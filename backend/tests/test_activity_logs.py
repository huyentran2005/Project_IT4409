import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.project import Project, Status
from app.models.project_member import ProjectMember
from app.models.project_role import Permission, ProjectRole, ProjectRolePermission
from app.models.task import ActivityLog, Task, TaskAssignee, TimeEntry, TaskComment
from app.models.user import User
from app.models.notification import Notification, NotificationSettings


class ActivityLogApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        for model in (User, Project, Permission, ProjectRole, ProjectRolePermission,
                      ProjectMember, Status, Task, TaskAssignee, ActivityLog, TimeEntry, TaskComment,
                      Notification, NotificationSettings):
            model.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.member = User(email="member@example.com", full_name="Nguyễn Thu Trang", is_active=True)
        self.outsider = User(email="outsider@example.com", full_name="Outside", is_active=True)
        self.db.add_all([self.member, self.outsider])
        self.db.flush()
        self.project = Project(owner_id=self.member.id, name="Project", key="TEST", description="")
        self.other_project = Project(owner_id=self.outsider.id, name="Other", key="OTHER", description="")
        self.db.add_all([self.project, self.other_project])
        self.db.flush()
        self.role = ProjectRole(project_id=self.project.id, code="viewer", name="Viewer", position=1)
        self.permission = Permission(code="project.view", name="Xem dự án")
        self.db.add_all([self.role, self.permission])
        self.db.flush()
        self.db.add_all([
            ProjectMember(project_id=self.project.id, user_id=self.member.id, role_id=self.role.id),
            ProjectRolePermission(role_id=self.role.id, permission_id=self.permission.id),
        ])
        self.db.commit()
        self.url = f"/api/projects/{self.project.id}/activity-logs"
        self.headers = {"Authorization": f"Bearer {create_access_token(str(self.member.id))}"}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def add_log(self, **overrides):
        values = dict(
            project_id=self.project.id, actor_id=self.member.id,
            entity_type="task", entity_id=uuid.uuid4(), action="created",
            description="đã tạo công việc", changes={"title": "Test"},
            created_at=datetime(2026, 11, 15, 3, tzinfo=timezone.utc),
        )
        values.update(overrides)
        entry = ActivityLog(**values)
        self.db.add(entry)
        self.db.flush()
        return entry

    def test_returns_project_logs_newest_first_with_frontend_fields(self):
        oldest = self.add_log()
        newest = self.add_log(
            action="deleted", changes={"title": "Test", "deletedAt": "2026-11-16"},
            created_at=oldest.created_at + timedelta(days=1),
        )
        self.add_log(project_id=self.other_project.id, description="Private other project")
        self.db.commit()
        response = self.client.get(self.url, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        logs = response.json()
        self.assertEqual([log["id"] for log in logs], [str(newest.id), str(oldest.id)])
        self.assertEqual(logs[0], {
            "id": str(newest.id), "actor": "Nguyễn Thu Trang", "actorInitials": "NT",
            "action": "deleted", "entityType": "task", "description": "đã tạo công việc",
            "createdAt": "2026-11-16T03:00:00Z", "changeCount": 2,
            "changeDetails": [
                {"field": "title", "label": "Tiêu đề", "hasPreviousValue": False, "oldValue": None, "newValue": "Test"},
                {"field": "deletedAt", "label": "Thời điểm xóa", "hasPreviousValue": False,
                 "oldValue": None, "newValue": "16/11/2026 07:00:00"},
            ],
        })

    def test_change_details_show_old_new_text_labels_names_and_dates(self):
        self.db.add(Status(project_id=self.project.id, code="review", name="Chờ nghiệm thu",
                           category="in_progress", color="#64748b", position=1000))
        self.add_log(action="updated", changes={
            "description": {"old": "Nội dung cũ\nDòng hai", "new": "Nội dung mới"},
            "priority": {"old": "medium", "new": "high"},
            "status": {"old": "backlog", "new": "review"},
            "assigneeIds": {"old": [str(self.member.id)], "new": [str(self.outsider.id)]},
            "reviewerId": {"old": None, "new": str(self.member.id)},
            "endDate": {"old": "2026-11-15", "new": "2026-11-20"},
            "overdueReason": {"old": "Chờ xác nhận", "new": None},
            "position": {"old": "1000.0000000000", "new": "0.0000000000"},
        })
        self.db.commit()
        response = self.client.get(self.url, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        details = {item["field"]: item for item in response.json()[0]["changeDetails"]}
        expected = {
            "description": ("Nội dung cũ\nDòng hai", "Nội dung mới"),
            "priority": ("Trung bình", "Cao"), "status": ("Cần làm", "Chờ nghiệm thu"),
            "assigneeIds": ("Nguyễn Thu Trang", "Outside"), "reviewerId": (None, "Nguyễn Thu Trang"),
            "endDate": ("15/11/2026", "20/11/2026"), "overdueReason": ("Chờ xác nhận", None),
            "position": ("1000", "0"),
        }
        self.assertEqual(len(details), len(expected))
        for field, (old, new) in expected.items():
            self.assertTrue(details[field]["hasPreviousValue"])
            self.assertEqual(details[field]["oldValue"], old)
            self.assertEqual(details[field]["newValue"], new)

    def test_comment_and_timesheet_details_and_legacy_snapshots(self):
        self.add_log(action="updated", changes={"comment": {
            "old": None, "new": {"id": str(uuid.uuid4()), "body": "Đã sửa lỗi\nKiểm tra lại"},
        }})
        self.add_log(action="logged_time", entity_type="timesheet", changes={
            "startTime": "2026-11-15T02:00:00Z", "endTime": "2026-11-15T03:30:00Z", "note": "Sửa lỗi",
        })
        self.add_log(action="created", changes={"priority": "low", "assigneeIds": []})
        self.db.commit()
        response = self.client.get(self.url, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        logs = {log["action"]: log for log in response.json()}
        self.assertEqual(logs["updated"]["changeDetails"][0]["newValue"], "Đã sửa lỗi\nKiểm tra lại")
        time_details = {item["field"]: item for item in logs["logged_time"]["changeDetails"]}
        self.assertEqual(time_details["startTime"]["newValue"], "15/11/2026 09:00:00")
        self.assertEqual(time_details["endTime"]["newValue"], "15/11/2026 10:30:00")
        self.assertEqual(time_details["note"]["newValue"], "Sửa lỗi")
        for item in logs["created"]["changeDetails"] + logs["logged_time"]["changeDetails"]:
            self.assertFalse(item["hasPreviousValue"])

    def test_missing_users_and_unknown_fields_do_not_break_details(self):
        self.outsider.deleted_at = datetime.now(timezone.utc)
        self.add_log(action="updated", changes={
            "reviewerId": {"old": str(uuid.uuid4()), "new": str(self.outsider.id)},
            "internal_field": "not for display",
        })
        self.add_log(action="updated", changes={})
        self.db.commit()
        response = self.client.get(self.url, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        details = [item for log in response.json() for item in log["changeDetails"]]
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["oldValue"], "Người dùng không còn tồn tại")
        self.assertEqual(details[0]["newValue"], "Outside (đã xóa)")

    def test_retains_logs_for_missing_and_soft_deleted_actors(self):
        self.add_log(actor_id=None, changes={})
        self.outsider.deleted_at = datetime.now(timezone.utc)
        self.add_log(actor_id=self.outsider.id, changes={})
        self.db.commit()
        response = self.client.get(self.url, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()), 2)
        for log in response.json():
            self.assertEqual(log["actor"], "Người dùng đã xóa")
            self.assertEqual(log["changeCount"], 0)

    def test_empty_project_returns_empty_array(self):
        response = self.client.get(self.url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_created_and_deleted_task_appear_in_log_api(self):
        permission = Permission(code="task.manage", name="Quản lý công việc")
        self.db.add(permission)
        self.db.flush()
        self.db.add_all([
            ProjectRolePermission(role_id=self.role.id, permission_id=permission.id),
            Status(project_id=self.project.id, code="backlog", name="Cần làm",
                   category="todo", color="#64748b", position=1000),
        ])
        self.db.commit()
        response = self.client.post(
            f"/api/projects/{self.project.id}/tasks", headers=self.headers,
            json={"title": "Kiểm tra nhật ký", "description": "Kiểm tra tạo và xóa",
                  "type": "task", "priority": "medium",
                  "startDate": "2026-11-15", "endDate": "2026-11-16",
                  "status": "backlog", "assigneeIds": []},
        )
        self.assertEqual(response.status_code, 201, response.text)
        task_id = response.json()["id"]
        response = self.client.delete(f"/api/tasks/{task_id}", headers=self.headers)
        self.assertEqual(response.status_code, 204, response.text)
        response = self.client.get(self.url, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        logs = response.json()
        self.assertEqual(len(logs), 2)
        self.assertEqual({log["action"] for log in logs}, {"created", "deleted"})
        for log in logs:
            self.assertEqual(log["entityType"], "task")
            self.assertIn("Kiểm tra nhật ký", log["description"])

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_outsider_cannot_read_logs(self):
        self.add_log()
        self.db.commit()
        headers = {"Authorization": f"Bearer {create_access_token(str(self.outsider.id))}"}
        self.assertEqual(self.client.get(self.url, headers=headers).status_code, 403)

    def test_member_without_view_permission_cannot_read_logs(self):
        self.db.query(ProjectRolePermission).delete()
        self.db.commit()
        self.assertEqual(self.client.get(self.url, headers=self.headers).status_code, 403)

    def test_deleted_project_cannot_be_read(self):
        self.add_log()
        self.project.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.assertEqual(self.client.get(self.url, headers=self.headers).status_code, 404)


if __name__ == "__main__":
    unittest.main()
