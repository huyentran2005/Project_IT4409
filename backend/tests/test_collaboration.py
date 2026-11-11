"""Test timesheet, bình luận và tiến độ (đổi trạng thái).

Chạy:  docker compose exec backend python -m unittest tests/test_collaboration.py -v
"""
import unittest
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models.collaboration import Comment, TimeEntry
from app.models.project import Project, Status
from app.models.project_member import ProjectMember
from app.models.project_role import Permission, ProjectRole, ProjectRolePermission
from app.models.task import ActivityLog, Task, TaskAssignee
from app.models.user import User
from tests import test_tasks as base


class CollaborationApiTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        for model in (
            User, Project, Permission, ProjectRole, ProjectRolePermission, ProjectMember,
            Status, Task, TaskAssignee, ActivityLog, Comment, TimeEntry,
        ):
            model.__table__.create(bind=self.engine, checkfirst=True)
        self.db = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)()

        def _override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = _override_get_db
        self.client = TestClient(app)
        # dùng lại dữ liệu mẫu (owner / member / viewer / outsider) của test_tasks
        self.seeded = base.TaskApiTestCase._seed_project(self)
        self.task_id = self._create_task()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _create_task(self) -> str:
        today = date.today()
        res = self.client.post(
            f"/api/projects/{self.seeded['project'].id}/tasks",
            json={
                "title": "Task thử nghiệm",
                "description": "Mô tả",
                "type": "task",
                "priority": "medium",
                "startDate": today.isoformat(),
                "endDate": (today + timedelta(days=3)).isoformat(),
                "assigneeIds": [str(self.seeded["member"].id)],
                "status": "backlog",
            },
            headers=base._auth_headers(self.seeded["owner"]),
        )
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()["id"]

    def _h(self, key: str) -> dict[str, str]:
        return base._auth_headers(self.seeded[key])

    # timesheet
    def test_log_time_by_date_and_hours(self):
        res = self.client.post(
            f"/api/tasks/{self.task_id}/timesheets",
            json={"date": date.today().isoformat(), "hours": 1.5, "isOvertime": True, "note": "Debug"},
            headers=self._h("member"),
        )
        self.assertEqual(res.status_code, 201, res.text)
        data = res.json()
        self.assertEqual(data["minutes"], 90)
        self.assertTrue(data["isOvertime"])
        self.assertEqual(data["taskKey"], "TF-1")
        self.assertEqual(
            self.db.query(ActivityLog).filter(ActivityLog.action == "logged_time").count(), 1
        )

    def test_log_time_by_range_and_validation(self):
        ok = self.client.post(
            f"/api/tasks/{self.task_id}/timesheets",
            json={"startTime": "2026-11-05T01:00:00Z", "endTime": "2026-11-05T03:30:00Z", "note": "Review PR"},
            headers=self._h("member"),
        )
        self.assertEqual(ok.status_code, 201, ok.text)
        self.assertEqual(ok.json()["minutes"], 150)

        bad_order = self.client.post(
            f"/api/tasks/{self.task_id}/timesheets",
            json={"startTime": "2026-11-05T03:00:00Z", "endTime": "2026-11-05T01:00:00Z"},
            headers=self._h("member"),
        )
        self.assertEqual(bad_order.status_code, 422)
        missing = self.client.post(f"/api/tasks/{self.task_id}/timesheets", json={}, headers=self._h("member"))
        self.assertEqual(missing.status_code, 422)
        too_many = self.client.post(
            f"/api/tasks/{self.task_id}/timesheets",
            json={"date": date.today().isoformat(), "hours": 25},
            headers=self._h("member"),
        )
        self.assertEqual(too_many.status_code, 422)

    def test_log_time_permissions(self):
        body = {"date": date.today().isoformat(), "hours": 1}
        url = f"/api/tasks/{self.task_id}/timesheets"
        self.assertEqual(self.client.post(url, json=body, headers=self._h("viewer")).status_code, 403)
        self.assertEqual(self.client.post(url, json=body, headers=self._h("outsider")).status_code, 403)
        self.assertEqual(self.client.post(url, json=body).status_code, 401)
        # viewer vẫn xem được
        self.assertEqual(self.client.get(url, headers=self._h("viewer")).status_code, 200)
        self.assertEqual(self.client.get(url, headers=self._h("outsider")).status_code, 403)

    def test_my_timesheets_filters_and_summary(self):
        today = date.today()
        for d, h, ot in ((today, 2, False), (today - timedelta(days=40), 3, False), (today, 1, True)):
            r = self.client.post(
                f"/api/tasks/{self.task_id}/timesheets",
                json={"date": d.isoformat(), "hours": h, "isOvertime": ot},
                headers=self._h("member"),
            )
            self.assertEqual(r.status_code, 201, r.text)

        everything = self.client.get("/api/timesheets", headers=self._h("member")).json()
        self.assertEqual(len(everything["entries"]), 3)
        self.assertEqual(everything["totalMinutes"], 6 * 60)

        recent = self.client.get(
            "/api/timesheets",
            params={"date_from": (today - timedelta(days=1)).isoformat(), "date_to": today.isoformat()},
            headers=self._h("member"),
        ).json()
        self.assertEqual(len(recent["entries"]), 2)

        ot_only = self.client.get("/api/timesheets", params={"overtime_only": "true"}, headers=self._h("member")).json()
        self.assertEqual(ot_only["overtimeMinutes"], 60)
        self.assertEqual(len(ot_only["entries"]), 1)

        # người khác không thấy bản ghi của member
        other = self.client.get("/api/timesheets", headers=self._h("owner")).json()
        self.assertEqual(other["entries"], [])

        summary = self.client.get("/api/timesheets/summary", headers=self._h("member")).json()
        self.assertEqual(summary["todayMinutes"], 180)
        self.assertEqual(summary["weekOvertimeMinutes"], 60)

    def test_delete_time_entry(self):
        entry = self.client.post(
            f"/api/tasks/{self.task_id}/timesheets",
            json={"date": date.today().isoformat(), "hours": 1},
            headers=self._h("member"),
        ).json()
        self.assertEqual(self.client.delete(f"/api/timesheets/{entry['id']}", headers=self._h("viewer")).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/timesheets/{entry['id']}", headers=self._h("member")).status_code, 204)
        self.assertEqual(self.client.delete(f"/api/timesheets/{entry['id']}", headers=self._h("member")).status_code, 404)

    # bình luận
    def test_comments_flow(self):
        url = f"/api/tasks/{self.task_id}/comments"
        created = self.client.post(url, json={"body": "  Đã xong phần API  "}, headers=self._h("member"))
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["body"], "Đã xong phần API")

        reply = self.client.post(
            url, json={"body": "Cảm ơn", "parentId": created.json()["id"]}, headers=self._h("viewer")
        )
        self.assertEqual(reply.status_code, 201, reply.text)

        listed = self.client.get(url, headers=self._h("owner")).json()
        self.assertEqual([c["body"] for c in listed], ["Đã xong phần API", "Cảm ơn"])
        self.assertEqual(self.client.post(url, json={"body": "   "}, headers=self._h("member")).status_code, 422)
        self.assertEqual(self.client.post(url, json={"body": "x"}, headers=self._h("outsider")).status_code, 403)

        cid = created.json()["id"]
        self.assertEqual(self.client.delete(f"/api/comments/{cid}", headers=self._h("viewer")).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/comments/{cid}", headers=self._h("member")).status_code, 204)
        self.assertEqual(len(self.client.get(url, headers=self._h("owner")).json()), 1)

    def test_board_contains_timesheets_and_comments(self):
        self.client.post(
            f"/api/tasks/{self.task_id}/timesheets",
            json={"date": date.today().isoformat(), "hours": 2, "note": "Làm API"},
            headers=self._h("member"),
        )
        self.client.post(f"/api/tasks/{self.task_id}/comments", json={"body": "Ổn"}, headers=self._h("member"))
        board = self.client.get(f"/api/projects/{self.seeded['project'].id}/board", headers=self._h("owner")).json()
        task = next(t for col in board["columns"] for t in col["tasks"] if t["id"] == self.task_id)
        self.assertEqual(task["comments"], 1)
        self.assertEqual(len(task["commentItems"]), 1)
        self.assertEqual(task["timesheets"][0]["minutes"], 120)

    #  tiến độ
    def test_move_task_progress(self):
        url = f"/api/tasks/{self.task_id}/move"
        owner, member, viewer = self._h("owner"), self._h("member"), self._h("viewer")

        self.assertEqual(self.client.patch(url, json={"status": "in-progress"}, headers=viewer).status_code, 403)
        self.assertEqual(self.client.patch(url, json={"status": "khong-co"}, headers=member).status_code, 400)

        moved = self.client.patch(url, json={"status": "in-progress", "position": 0}, headers=member)
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(moved.json()["status"], "in-progress")

        # vào 'review' bắt buộc có người duyệt
        self.assertEqual(self.client.patch(url, json={"status": "review"}, headers=member).status_code, 400)
        review = self.client.patch(
            url, json={"status": "review", "reviewerId": str(self.seeded["owner"].id)}, headers=member
        )
        self.assertEqual(review.status_code, 200, review.text)
        self.assertEqual(review.json()["reviewer"]["id"], str(self.seeded["owner"].id))

        done = self.client.patch(url, json={"status": "done"}, headers=owner)
        self.assertEqual(done.status_code, 200, done.text)
        self.assertIsNotNone(done.json()["completedAt"])

        board = self.client.get(f"/api/projects/{self.seeded['project'].id}/board", headers=owner).json()
        self.assertEqual(board["project"]["progress"], 100)

        reopened = self.client.patch(url, json={"status": "backlog"}, headers=owner).json()
        self.assertIsNone(reopened["completedAt"])

    def test_move_overdue_task_to_done_requires_reason(self):
        props = f"/api/tasks/{self.task_id}/properties"
        past = date.today() - timedelta(days=10)
        r = self.client.patch(
            props,
            json={"startDate": (past - timedelta(days=2)).isoformat(), "endDate": past.isoformat()},
            headers=self._h("owner"),
        )
        self.assertEqual(r.status_code, 200, r.text)
        move = f"/api/tasks/{self.task_id}/move"
        self.assertEqual(self.client.patch(move, json={"status": "done"}, headers=self._h("owner")).status_code, 400)
        ok = self.client.patch(
            move, json={"status": "done", "overdueReason": "Chờ khách hàng"}, headers=self._h("owner")
        )
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(ok.json()["overdueReason"], "Chờ khách hàng")

    def test_update_properties_and_reviewer(self):
        owner = self._h("owner")
        props = self.client.patch(
            f"/api/tasks/{self.task_id}/properties",
            json={
                "description": "Mô tả mới",
                "priority": "urgent",
                "assigneeIds": [str(self.seeded["owner"].id)],
                "acceptanceResult": "Đạt",
            },
            headers=owner,
        )
        self.assertEqual(props.status_code, 200, props.text)
        data = props.json()
        self.assertEqual(data["priority"], "urgent")
        self.assertEqual([a["id"] for a in data["assignees"]], [str(self.seeded["owner"].id)])
        self.assertEqual(data["acceptanceResult"], "Đạt")

        outsider_assignee = self.client.patch(
            f"/api/tasks/{self.task_id}/properties",
            json={"assigneeIds": [str(self.seeded["outsider"].id)]},
            headers=owner,
        )
        self.assertEqual(outsider_assignee.status_code, 400)
        bad_dates = self.client.patch(
            f"/api/tasks/{self.task_id}/properties",
            json={"startDate": "2026-12-10", "endDate": "2026-12-01"},
            headers=owner,
        )
        self.assertEqual(bad_dates.status_code, 400)

        reviewer = self.client.patch(
            f"/api/tasks/{self.task_id}/reviewer",
            json={"reviewerId": str(self.seeded["member"].id)},
            headers=owner,
        )
        self.assertEqual(reviewer.status_code, 200, reviewer.text)
        self.assertEqual(reviewer.json()["reviewer"]["id"], str(self.seeded["member"].id))


if __name__ == "__main__":
    unittest.main()
