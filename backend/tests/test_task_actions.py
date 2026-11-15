import uuid
from datetime import date, timedelta

from sqlalchemy import event

from app.models.task import ActivityLog, Task, TaskComment, TimeEntry
from test_tasks import TaskApiFixture, _auth_headers


class TaskActionTests(TaskApiFixture):
    def setUp(self):
        super().setUp()
        self.headers = _auth_headers(self.seeded["member"])
        self.project_id = self.seeded["project"].id
        self.project_url = f"/api/projects/{self.project_id}"
        today = date.today()
        response = self.client.post(self.project_url + "/tasks", headers=self.headers, json={
            "title": "Task để kiểm tra", "description": "Mô tả ban đầu",
            "startDate": today.isoformat(), "endDate": (today + timedelta(days=10)).isoformat(),
            "assigneeIds": [str(self.seeded["member"].id)],
        })
        self.assertEqual(response.status_code, 201, response.text)
        self.task_id = uuid.UUID(response.json()["id"])
        self.url = f"/api/tasks/{self.task_id}"

    def logs(self):
        return self.db.query(ActivityLog).filter(ActivityLog.project_id == self.project_id).all()

    def board_task(self):
        response = self.client.get(self.project_url + "/board", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return next(task for column in response.json()["columns"] for task in column["tasks"]
                    if task["id"] == str(self.task_id))

    def test_update_persists_and_logs_old_new_values_without_noop_logs(self):
        payload = {"description": "Mô tả mới", "priority": "high",
                   "assigneeIds": [str(self.seeded["owner"].id)], "acceptanceResult": "Đã kiểm tra"}
        response = self.client.patch(self.url + "/properties", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.board_task()["description"], "Mô tả mới")
        self.assertEqual(response.json()["assignees"][0]["id"], str(self.seeded["owner"].id))
        updated = next(log for log in self.logs() if log.action == "updated")
        self.assertEqual(updated.actor_id, self.seeded["member"].id)
        self.assertEqual(updated.changes["description"], {"old": "Mô tả ban đầu", "new": "Mô tả mới"})
        response = self.client.patch(self.url + "/properties", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.logs()), 2)
        response = self.client.patch(self.url, headers=self.headers, json={"title": "Tên mới", "type": "bug"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.board_task()["title"], "Tên mới")

    def test_move_reviewer_completion_and_reopen_are_persisted(self):
        response = self.client.patch(self.url + "/move", headers=self.headers, json={"status": "review"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.board_task()["status"], "backlog")
        response = self.client.patch(self.url + "/move", headers=self.headers, json={
            "status": "review", "reviewerId": str(self.seeded["owner"].id), "position": 0,
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.board_task()["reviewer"]["id"], str(self.seeded["owner"].id))
        response = self.client.patch(self.url + "/move", headers=self.headers, json={"status": "done"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(response.json()["completedAt"])
        response = self.client.patch(self.url + "/move", headers=self.headers, json={"status": "in-progress"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(self.board_task()["completedAt"])
        self.assertEqual(len([log for log in self.logs() if "status" in log.changes]), 4)  # includes creation

    def test_reviewer_endpoint_and_noop(self):
        payload = {"reviewerId": str(self.seeded["owner"].id)}
        for _ in range(2):
            response = self.client.patch(self.url + "/reviewer", headers=self.headers, json=payload)
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.logs()), 2)
        self.assertEqual(self.board_task()["reviewer"]["id"], payload["reviewerId"])

    def test_comments_and_time_survive_reload_and_have_activity(self):
        comment = self.client.post(self.url + "/comments", headers=self.headers, json={"body": " Đã kiểm tra "})
        self.assertEqual(comment.status_code, 201, comment.text)
        entry = self.client.post(self.url + "/timesheets", headers=self.headers, json={
            "startTime": "2026-11-15T09:00:00+07:00", "endTime": "2026-11-15T10:30:00+07:00", "note": "Làm việc",
        })
        self.assertEqual(entry.status_code, 201, entry.text)
        self.assertEqual(entry.json()["minutes"], 90)
        self.assertEqual(entry.json()["user"]["id"], str(self.seeded["member"].id))
        self.db.expire_all()
        task = self.board_task()
        self.assertEqual(task["comments"], 1)
        self.assertEqual(task["commentItems"][0]["body"], "Đã kiểm tra")
        self.assertEqual(task["timesheets"][0]["id"], entry.json()["id"])
        for suffix, expected in [("comments", comment.json()), ("timesheets", entry.json())]:
            response = self.client.get(self.url + "/" + suffix, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), [expected])
        log = next(log for log in self.logs() if log.action == "logged_time")
        self.assertEqual(log.entity_type, "timesheet")
        self.assertEqual(str(log.entity_id), entry.json()["id"])
        self.assertTrue(any("comment" in log.changes for log in self.logs()))

    def test_invalid_inputs_do_not_write_or_log(self):
        for suffix, payload, code in [
            ("/properties", {"description": "   "}, 422),
            ("/properties", {"priority": None}, 422),
            ("/properties", {"endDate": "2000-01-01"}, 400),
            ("/properties", {"assigneeIds": [str(self.seeded["outsider"].id)]}, 400),
            ("/reviewer", {"reviewerId": str(self.seeded["outsider"].id)}, 400),
            ("/move", {"status": "missing"}, 400),
        ]:
            with self.subTest(suffix=suffix, payload=payload):
                response = self.client.patch(self.url + suffix, headers=self.headers, json=payload)
                self.assertEqual(response.status_code, code, response.text)
        for suffix, payload in [
            ("/comments", {"body": "   "}),
            ("/comments", {"body": "text", "author_id": str(self.seeded["owner"].id)}),
            ("/timesheets", {"startTime": "2026-11-15T10:00:00Z", "endTime": "2026-11-15T09:00:00Z", "note": "test"}),
            ("/timesheets", {"startTime": "2026-11-15T09:00:00", "endTime": "2026-11-15T10:00:00", "note": "test"}),
        ]:
            self.assertEqual(self.client.post(self.url + suffix, headers=self.headers, json=payload).status_code, 422)
        self.assertEqual(len(self.logs()), 1)
        self.assertEqual(self.db.query(TaskComment).count(), 0)
        self.assertEqual(self.db.query(TimeEntry).count(), 0)

    def test_permissions_for_writes_and_reads(self):
        for person in ("viewer", "outsider"):
            headers = _auth_headers(self.seeded[person])
            for suffix, payload in [("/properties", {"priority": "high"}), ("/move", {"status": "done"}),
                                    ("/reviewer", {"reviewerId": str(self.seeded["owner"].id)})]:
                self.assertEqual(self.client.patch(self.url + suffix, headers=headers, json=payload).status_code, 403)
            for suffix, payload in [("/comments", {"body": "test"}), ("/timesheets", {
                "startTime": "2026-11-15T09:00:00Z", "endTime": "2026-11-15T10:00:00Z", "note": "test"})]:
                self.assertEqual(self.client.post(self.url + suffix, headers=headers, json=payload).status_code, 403)
            for suffix in ("/comments", "/timesheets"):
                self.assertEqual(self.client.get(self.url + suffix, headers=headers).status_code, 200 if person == "viewer" else 403)
        self.assertEqual(self.client.patch(self.url, json={"priority": "high"}).status_code, 401)
        self.assertEqual(len(self.logs()), 1)

    def test_overdue_move_requires_reason(self):
        task = self.db.get(Task, self.task_id)
        task.start_date = date.today() - timedelta(days=3)
        task.end_date = date.today() - timedelta(days=2)
        self.db.commit()
        response = self.client.patch(self.url + "/move", headers=self.headers, json={"status": "done"})
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(self.url + "/move", headers=self.headers,
                                     json={"status": "done", "overdueReason": "Chờ phản hồi"})
        self.assertEqual(response.status_code, 200, response.text)

    def test_log_failure_rolls_back_task_comment_and_time(self):
        def fail_log(*args):
            raise RuntimeError("Simulated log failure")
        event.listen(ActivityLog, "before_insert", fail_log)
        try:
            for method, suffix, payload in [
                ("patch", "/properties", {"description": "Must roll back"}),
                ("post", "/comments", {"body": "Must roll back"}),
                ("post", "/timesheets", {"startTime": "2026-11-15T09:00:00Z", "endTime": "2026-11-15T10:00:00Z", "note": "test"}),
            ]:
                with self.assertRaisesRegex(RuntimeError, "Simulated log failure"):
                    getattr(self.client, method)(self.url + suffix, headers=self.headers, json=payload)
                self.assertEqual(self.db.get(Task, self.task_id).description, "Mô tả ban đầu")
                self.assertEqual(self.db.query(TaskComment).count(), 0)
                self.assertEqual(self.db.query(TimeEntry).count(), 0)
                self.assertEqual(len(self.logs()), 1)
        finally:
            event.remove(ActivityLog, "before_insert", fail_log)

    def test_deleted_task_and_archived_project_reject_writes(self):
        project = self.seeded["project"]
        project.is_archived = True
        self.db.commit()
        self.assertEqual(self.client.patch(self.url, headers=self.headers, json={"priority": "high"}).status_code, 400)
        project.is_archived = False
        self.db.commit()
        self.assertEqual(self.client.delete(self.url, headers=self.headers).status_code, 204)
        self.assertEqual(self.client.patch(self.url, headers=self.headers, json={"priority": "high"}).status_code, 404)
