import unittest
import uuid
from datetime import date, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.models.project import (
    Project,
    Permission,
    ProjectRole,
    ProjectRolePermission,
    ProjectMember,
    Status,
)
from app.models.task import Task, TaskAssignee, ActivityLog


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


class TaskApiTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        tables = [
            User.__table__,
            Project.__table__,
            Permission.__table__,
            ProjectRole.__table__,
            ProjectRolePermission.__table__,
            ProjectMember.__table__,
            Status.__table__,
            Task.__table__,
            TaskAssignee.__table__,
            ActivityLog.__table__,
        ]
        for table in tables:
            table.create(bind=self.engine, checkfirst=True)

        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self.db = TestingSessionLocal()

        def _override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = _override_get_db
        self.client = TestClient(app)
        self.seeded = self._seed_project()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _seed_project(self):
        owner = User(
            email="owner@taskflow.vn",
            full_name="Nguyễn Thu Trang",
            avatar_color="#5B5CE2",
            is_active=True,
        )
        member_user = User(
            email="member@taskflow.vn",
            full_name="Trần Minh Quân",
            avatar_color="#0F9F8F",
            is_active=True,
        )
        viewer_user = User(
            email="viewer@taskflow.vn",
            full_name="Lê Hoàng Nam",
            avatar_color="#D97706",
            is_active=True,
        )
        outsider_user = User(
            email="outsider@taskflow.vn",
            full_name="Phạm Khách",
            avatar_color="#64748B",
            is_active=True,
        )
        self.db.add_all([owner, member_user, viewer_user, outsider_user])
        self.db.flush()

        project = Project(
            owner_id=owner.id,
            name="TaskFlow Core",
            key="TF",
            description="Dự án phát triển hệ thống quản lý công việc TaskFlow",
            color="#5B5CE2",
            task_sequence=0,
        )
        self.db.add(project)
        self.db.flush()

        perm_task_manage = Permission(
            code="task.manage",
            name="Quản lý công việc",
            description="Tạo, sửa và di chuyển công việc",
        )
        perm_project_view = Permission(
            code="project.view",
            name="Xem dự án",
            description="Xem bảng, thành viên và tài liệu",
        )
        self.db.add_all([perm_task_manage, perm_project_view])
        self.db.flush()

        role_owner = ProjectRole(
            project_id=project.id,
            code="owner",
            name="Owner",
            is_system=True,
            position=1,
        )
        role_member = ProjectRole(
            project_id=project.id,
            code="member",
            name="Member",
            is_system=True,
            position=2,
        )
        role_viewer = ProjectRole(
            project_id=project.id,
            code="viewer",
            name="Viewer",
            is_system=True,
            position=3,
        )
        self.db.add_all([role_owner, role_member, role_viewer])
        self.db.flush()

        self.db.add_all(
            [
                ProjectRolePermission(
                    role_id=role_owner.id, permission_id=perm_task_manage.id
                ),
                ProjectRolePermission(
                    role_id=role_owner.id, permission_id=perm_project_view.id
                ),
                ProjectRolePermission(
                    role_id=role_member.id, permission_id=perm_task_manage.id
                ),
                ProjectRolePermission(
                    role_id=role_member.id, permission_id=perm_project_view.id
                ),
                ProjectRolePermission(
                    role_id=role_viewer.id, permission_id=perm_project_view.id
                ),
            ]
        )

        self.db.add_all(
            [
                ProjectMember(
                    project_id=project.id, user_id=owner.id, role_id=role_owner.id
                ),
                ProjectMember(
                    project_id=project.id,
                    user_id=member_user.id,
                    role_id=role_member.id,
                ),
                ProjectMember(
                    project_id=project.id,
                    user_id=viewer_user.id,
                    role_id=role_viewer.id,
                ),
            ]
        )

        statuses = [
            Status(
                project_id=project.id,
                code="backlog",
                name="Cần làm",
                category="todo",
                color="#64748b",
                position=Decimal("1000"),
                wip_limit=8,
            ),
            Status(
                project_id=project.id,
                code="in-progress",
                name="Đang làm",
                category="in_progress",
                color="#2563eb",
                position=Decimal("2000"),
                wip_limit=2,
            ),
            Status(
                project_id=project.id,
                code="review",
                name="Đang duyệt",
                category="in_progress",
                color="#d97706",
                position=Decimal("3000"),
                wip_limit=3,
            ),
            Status(
                project_id=project.id,
                code="done",
                name="Hoàn thành",
                category="done",
                color="#0f9f8f",
                position=Decimal("4000"),
                wip_limit=None,
            ),
        ]
        self.db.add_all(statuses)
        self.db.commit()

        return {
            "project": project,
            "owner": owner,
            "member": member_user,
            "viewer": viewer_user,
            "outsider": outsider_user,
        }

    def test_create_task_success(self):
        project = self.seeded["project"]
        member = self.seeded["member"]
        owner = self.seeded["owner"]

        today = date.today()
        payload = {
            "title": "Thiết kế API tạo và xóa công việc",
            "description": "Xây dựng endpoint POST /projects/{id}/tasks và DELETE /tasks/{id}",
            "type": "task",
            "priority": "high",
            "startDate": today.isoformat(),
            "endDate": (today + timedelta(days=5)).isoformat(),
            "assigneeIds": [str(member.id), str(owner.id)],
            "status": "backlog",
        }

        res = self.client.post(
            f"/api/projects/{project.id}/tasks",
            json=payload,
            headers=_auth_headers(member),
        )
        self.assertEqual(res.status_code, 201, res.text)
        data = res.json()
        self.assertEqual(data["key"], "TF-1")
        self.assertEqual(data["title"], payload["title"])
        self.assertEqual(data["type"], "task")
        self.assertEqual(data["priority"], "high")
        self.assertEqual(data["status"], "backlog")
        self.assertEqual(len(data["assignees"]), 2)
        self.assertEqual(
            {a["id"] for a in data["assignees"]}, {str(member.id), str(owner.id)}
        )

        logs = (
            self.db.query(ActivityLog)
            .filter(
                ActivityLog.project_id == project.id,
                ActivityLog.action == "created",
            )
            .all()
        )
        self.assertEqual(len(logs), 1)

    def test_create_task_invalid_dates(self):
        project = self.seeded["project"]
        owner = self.seeded["owner"]
        today = date.today()

        res = self.client.post(
            f"/api/projects/{project.id}/tasks",
            json={
                "title": "Task lỗi ngày",
                "description": "EndDate trước StartDate",
                "type": "bug",
                "priority": "urgent",
                "startDate": today.isoformat(),
                "endDate": (today - timedelta(days=1)).isoformat(),
                "assigneeIds": [],
                "status": "backlog",
            },
            headers=_auth_headers(owner),
        )
        self.assertEqual(res.status_code, 422)

    def test_create_task_forbidden_for_viewer_and_outsider(self):
        project = self.seeded["project"]
        viewer = self.seeded["viewer"]
        outsider = self.seeded["outsider"]
        today = date.today()

        body = {
            "title": "Task kiểm tra phân quyền",
            "description": "Viewer không có quyền task.manage",
            "type": "task",
            "priority": "medium",
            "startDate": today.isoformat(),
            "endDate": today.isoformat(),
            "assigneeIds": [],
            "status": "backlog",
        }

        res_viewer = self.client.post(
            f"/api/projects/{project.id}/tasks",
            json=body,
            headers=_auth_headers(viewer),
        )
        self.assertEqual(res_viewer.status_code, 403)

        res_outsider = self.client.post(
            f"/api/projects/{project.id}/tasks",
            json=body,
            headers=_auth_headers(outsider),
        )
        self.assertEqual(res_outsider.status_code, 403)

    def test_create_task_rejects_non_member_assignee(self):
        project = self.seeded["project"]
        owner = self.seeded["owner"]
        outsider = self.seeded["outsider"]
        today = date.today()

        res = self.client.post(
            f"/api/projects/{project.id}/tasks",
            json={
                "title": "Giao việc cho người ngoài dự án",
                "description": "Phải báo lỗi 400",
                "type": "task",
                "priority": "low",
                "startDate": today.isoformat(),
                "endDate": today.isoformat(),
                "assigneeIds": [str(outsider.id)],
                "status": "backlog",
            },
            headers=_auth_headers(owner),
        )
        self.assertEqual(res.status_code, 400)

    def test_delete_task_soft_delete_and_idempotency(self):
        project = self.seeded["project"]
        owner = self.seeded["owner"]
        viewer = self.seeded["viewer"]
        today = date.today()

        create_res = self.client.post(
            f"/api/projects/{project.id}/tasks",
            json={
                "title": "Task chuẩn bị xóa",
                "description": "Kiểm tra xóa mềm deleted_at",
                "type": "story",
                "priority": "medium",
                "startDate": today.isoformat(),
                "endDate": today.isoformat(),
                "assigneeIds": [str(owner.id)],
                "status": "backlog",
            },
            headers=_auth_headers(owner),
        )
        self.assertEqual(create_res.status_code, 201)
        task_id = create_res.json()["id"]

        res_forbidden = self.client.delete(
            f"/api/tasks/{task_id}",
            headers=_auth_headers(viewer),
        )
        self.assertEqual(res_forbidden.status_code, 403)

        res_del = self.client.delete(
            f"/api/tasks/{task_id}",
            headers=_auth_headers(owner),
        )
        self.assertEqual(res_del.status_code, 204)

        task_in_db = (
            self.db.query(Task).filter(Task.id == uuid.UUID(task_id)).first()
        )
        self.assertIsNotNone(task_in_db)
        self.assertIsNotNone(task_in_db.deleted_at)

        res_del_again = self.client.delete(
            f"/api/tasks/{task_id}",
            headers=_auth_headers(owner),
        )
        self.assertEqual(res_del_again.status_code, 404)

    def test_get_board_and_auto_bootstrap_for_new_user(self):
        outsider = self.seeded["outsider"]
        # Outsider chưa có dự án nào, khi FE gọi /api/projects/p-01/board sẽ tự khởi tạo dự án mặc định
        board_res = self.client.get(
            "/api/projects/p-01/board",
            headers=_auth_headers(outsider),
        )
        self.assertEqual(board_res.status_code, 200, board_res.text)
        board = board_res.json()
        self.assertEqual(len(board["columns"]), 4)
        project_id = board["project"]["id"]

        today = date.today()
        create_res = self.client.post(
            f"/api/projects/{project_id}/tasks",
            json={
                "title": "Task tạo trực tiếp từ giao diện FE",
                "description": "Hiển thị trên cột Cần làm",
                "type": "task",
                "priority": "high",
                "startDate": today.isoformat(),
                "endDate": today.isoformat(),
                "assigneeIds": [str(outsider.id)],
                "status": "backlog",
            },
            headers=_auth_headers(outsider),
        )
        self.assertEqual(create_res.status_code, 201, create_res.text)

        board_after = self.client.get(
            f"/api/projects/{project_id}/board",
            headers=_auth_headers(outsider),
        ).json()
        backlog_col = next(c for c in board_after["columns"] if c["id"] == "backlog")
        self.assertEqual(len(backlog_col["tasks"]), 1)
        self.assertEqual(
            backlog_col["tasks"][0]["title"], "Task tạo trực tiếp từ giao diện FE"
        )


if __name__ == "__main__":
    unittest.main()
