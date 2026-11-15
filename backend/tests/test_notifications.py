import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import event

from app.models.notification import Notification, NotificationSettings
from app.models.project_member import ProjectMember
from app.models.project_role import ProjectRolePermission
from app.models.task import ActivityLog, Task
from test_tasks import TaskApiFixture, _auth_headers


class NotificationTests(TaskApiFixture):
    def setUp(self):
        super().setUp()
        self.owner_headers = _auth_headers(self.seeded['owner'])
        self.member_headers = _auth_headers(self.seeded['member'])
        self.viewer_headers = _auth_headers(self.seeded['viewer'])
        self.project_id = self.seeded['project'].id
        today = date.today()
        response = self.client.post(f'/api/projects/{self.project_id}/tasks', headers=self.owner_headers, json={
            'title': 'Notification task', 'description': 'Initial', 'startDate': today.isoformat(),
            'endDate': (today + timedelta(days=5)).isoformat(), 'assigneeIds': [str(self.seeded['member'].id)],
        })
        self.assertEqual(response.status_code, 201, response.text)
        self.task_id = response.json()['id']
        self.url = '/api/tasks/' + self.task_id

    def inbox(self, headers=None, params=None):
        response = self.client.get('/api/notifications', headers=headers or self.member_headers, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_assignment_and_no_self_or_unrelated_notifications(self):
        box = self.inbox()
        self.assertEqual(box['unreadCount'], 1)
        self.assertEqual(box['items'][0]['type'], 'task_assigned')
        self.assertEqual(box['items'][0]['taskId'], self.task_id)
        self.assertEqual(self.inbox(self.owner_headers)['items'], [])
        self.assertEqual(self.inbox(self.viewer_headers)['items'], [])
        self.assertEqual(self.client.get(self.url, headers=self.member_headers).status_code, 200)
        outsider = _auth_headers(self.seeded['outsider'])
        self.assertEqual(self.client.get(self.url, headers=outsider).status_code, 403)

    def test_updates_reviewer_status_comments_time_and_delete(self):
        response = self.client.patch(self.url + '/reviewer', headers=self.owner_headers,
                                     json={'reviewerId': str(self.seeded['viewer'].id)})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.inbox(self.viewer_headers)['items'][0]['type'], 'task_review_requested')
        self.assertEqual(self.inbox()['unreadCount'], 2)
        before = self.db.query(Notification).count()
        self.client.patch(self.url + '/reviewer', headers=self.owner_headers, json={'reviewerId': str(self.seeded['viewer'].id)})
        self.assertEqual(self.db.query(Notification).count(), before)
        calls = [
            ('patch', '/properties', {'priority': 'high'}, 'task_updated'),
            ('patch', '/move', {'status': 'review'}, 'task_status_changed'),
            ('post', '/comments', {'body': 'Please review'}, 'task_comment'),
            ('post', '/timesheets', {'startTime': '2026-11-15T09:00:00Z', 'endTime': '2026-11-15T10:00:00Z', 'note': 'Work'}, 'task_time_logged'),
        ]
        for method, suffix, body, kind in calls:
            response = getattr(self.client, method)(self.url + suffix, headers=self.member_headers, json=body)
            self.assertIn(response.status_code, (200, 201), response.text)
            self.assertTrue(any(item['type'] == kind for item in self.inbox(self.owner_headers)['items']))
        self.assertEqual(self.client.delete(self.url, headers=self.owner_headers).status_code, 204)
        deleted = [item for item in self.inbox()['items'] if item['type'] == 'task_deleted']
        self.assertEqual(len(deleted), 1)
        self.assertTrue(deleted[0]['taskDeleted'])
        self.assertEqual(self.client.get(self.url, headers=self.member_headers).status_code, 404)

    def test_mark_read_is_owner_only_idempotent_and_persistent(self):
        item = self.inbox()['items'][0]
        url = f"/api/notifications/{item['id']}/read"
        self.assertEqual(self.client.patch(url, headers=self.owner_headers).status_code, 404)
        first = self.client.patch(url, headers=self.member_headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.client.patch(url, headers=self.member_headers).json()['readAt'], first.json()['readAt'])
        self.db.expire_all()
        self.assertEqual(self.inbox()['unreadCount'], 0)
        self.assertIsNotNone(self.inbox()['items'][0]['readAt'])
        self.assertEqual(self.client.get('/api/notifications').status_code, 401)
        self.assertEqual(self.client.patch('/api/notifications/read-all').status_code, 401)

    def test_read_all_scoped_and_pagination_newest_first(self):
        for index in range(25):
            self.db.add(Notification(user_id=self.seeded['member'].id, project_id=self.project_id,
                type='task_updated', title=f'item {index}', payload={},
                created_at=datetime(2030, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=index)))
        other = Notification(user_id=self.seeded['owner'].id, project_id=self.project_id,
                             type='task_updated', title='other inbox', payload={})
        self.db.add(other)
        self.db.commit()
        first = self.inbox(params={'limit': 20})
        second = self.inbox(params={'limit': 20, 'offset': 20})
        self.assertEqual(first['items'][0]['title'], 'item 24')
        self.assertEqual(first['unreadCount'], 26)
        self.assertTrue(first['hasMore'])
        self.assertFalse(second['hasMore'])
        self.assertEqual(len(second['items']), 6)
        self.assertFalse({item['id'] for item in first['items']} & {item['id'] for item in second['items']})
        self.assertEqual(self.client.patch('/api/notifications/read-all', headers=self.member_headers).status_code, 204)
        self.assertEqual(self.inbox()['unreadCount'], 0)
        self.assertEqual(self.inbox(self.owner_headers)['unreadCount'], 1)

    def test_revoked_membership_hides_history_and_stops_delivery(self):
        item = self.inbox()['items'][0]
        self.db.query(ProjectMember).filter(ProjectMember.project_id == self.project_id,
            ProjectMember.user_id == self.seeded['member'].id).delete()
        self.db.commit()
        self.assertEqual(self.inbox()['items'], [])
        self.assertEqual(self.client.patch(f"/api/notifications/{item['id']}/read", headers=self.member_headers).status_code, 404)
        response = self.client.patch(self.url, headers=self.owner_headers, json={'priority': 'high'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.db.query(Notification).count(), 1)

    def test_opt_out_and_revoked_permission(self):
        self.db.add(NotificationSettings(user_id=self.seeded['member'].id, in_app_enabled=False))
        self.db.commit()
        self.client.patch(self.url, headers=self.owner_headers, json={'priority': 'high'})
        self.assertEqual(self.db.query(Notification).count(), 1)
        self.db.query(NotificationSettings).delete()
        member = self.db.query(ProjectMember).filter(ProjectMember.user_id == self.seeded['member'].id).one()
        self.db.query(ProjectRolePermission).filter(ProjectRolePermission.role_id == member.role_id).delete()
        self.db.commit()
        self.assertEqual(self.inbox()['unreadCount'], 0)
        self.client.patch(self.url, headers=self.owner_headers, json={'priority': 'low'})
        self.assertEqual(self.db.query(Notification).count(), 1)

    def test_inactive_user_and_deleted_project(self):
        self.seeded['member'].is_active = False
        self.db.commit()
        response = self.client.patch(self.url, headers=self.owner_headers, json={'priority': 'high'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.db.query(Notification).count(), 1)
        self.seeded['member'].is_active = True
        self.seeded['project'].deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.assertEqual(self.inbox()['items'], [])
        self.assertEqual(self.inbox()['unreadCount'], 0)

    def test_reassignment_notifies_removed_and_added_once(self):
        response = self.client.patch(self.url, headers=self.owner_headers,
            json={'assigneeIds': [str(self.seeded['viewer'].id), str(self.seeded['viewer'].id)]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.inbox(self.viewer_headers)['unreadCount'], 1)
        self.assertEqual(self.inbox(self.viewer_headers)['items'][0]['type'], 'task_assigned')
        self.assertEqual(self.inbox()['unreadCount'], 2)

    def test_notification_failure_rolls_back_task_and_log(self):
        def fail(*args):
            raise RuntimeError('notification failed')
        count = self.db.query(ActivityLog).count()
        event.listen(Notification, 'before_insert', fail)
        try:
            with self.assertRaisesRegex(RuntimeError, 'notification failed'):
                self.client.patch(self.url, headers=self.owner_headers, json={'description': 'Must roll back'})
            self.assertEqual(self.db.get(Task, uuid.UUID(self.task_id)).description, 'Initial')
            self.assertEqual(self.db.query(ActivityLog).count(), count)
            self.assertEqual(self.inbox()['unreadCount'], 1)
        finally:
            event.remove(Notification, 'before_insert', fail)
