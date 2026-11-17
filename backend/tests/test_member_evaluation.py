import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.notification import Notification, NotificationSettings
from app.models.project import Project, Status
from app.models.project_member import ProjectMember
from app.models.project_role import Permission, ProjectRole, ProjectRolePermission
from app.models.task import ActivityLog, Task, TaskAssignee, TaskComment, TimeEntry
from app.models.user import User
from app.services import evaluation_service as svc

UTC = timezone.utc
DEADLINE = date(2026, 11, 10)   # mốc hạn dùng chung cho các test


def at(day: int, hour: int = 3, month: int = 11) -> datetime:
    """Thời điểm UTC. 03:00 UTC = 10:00 giờ Việt Nam cùng ngày."""
    return datetime(2026, month, day, hour, tzinfo=UTC)


def headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


class EvaluationFixture(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        for model in (User, Project, Permission, ProjectRole, ProjectRolePermission, ProjectMember, Status,
                      Task, TaskAssignee, ActivityLog, TimeEntry, TaskComment, Notification,
                      NotificationSettings):
            model.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

        self.reviewer = User(email="reviewer@example.com", full_name="Zed Reviewer", is_active=True)
        self.alice = User(email="alice@example.com", full_name="Alice An", is_active=True)
        self.bob = User(email="bob@example.com", full_name="Bob Bình", is_active=True)
        self.outsider = User(email="out@example.com", full_name="Outsider", is_active=True)
        self.db.add_all([self.reviewer, self.alice, self.bob, self.outsider])
        self.db.flush()
        self.project = Project(owner_id=self.reviewer.id, name="Eval", key="eval", description="d",
                               timezone="Asia/Ho_Chi_Minh")
        self.db.add(self.project)
        self.db.flush()

        view = Permission(code="project.view", name="Xem dự án")
        manage = Permission(code="member.manage", name="Quản lý thành viên")
        manager = ProjectRole(project_id=self.project.id, code="manager", name="Manager", is_system=True, position=1)
        member = ProjectRole(project_id=self.project.id, code="member", name="Member", is_system=True, position=2)
        self.db.add_all([view, manage, manager, member])
        self.db.flush()
        self.db.add_all([
            ProjectRolePermission(role_id=manager.id, permission_id=view.id),
            ProjectRolePermission(role_id=manager.id, permission_id=manage.id),
            ProjectRolePermission(role_id=member.id, permission_id=view.id),
            ProjectMember(project_id=self.project.id, user_id=self.reviewer.id, role_id=manager.id),
            ProjectMember(project_id=self.project.id, user_id=self.alice.id, role_id=member.id),
            ProjectMember(project_id=self.project.id, user_id=self.bob.id, role_id=member.id),
        ])
        self.st = {}
        for code, name, category, position in (
            ("backlog", "Cần làm", "todo", 1000), ("in-progress", "Đang làm", "in_progress", 2000),
            ("review", "Đang duyệt", "in_progress", 3000), ("done", "Hoàn thành", "done", 4000),
            ("testing", "Kiểm thử", "in_progress", 3500),
        ):
            self.st[code] = Status(project_id=self.project.id, code=code, name=name, category=category,
                                   color="#000000", position=Decimal(position))
            self.db.add(self.st[code])
        self.db.commit()
        self.number = 0

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    # ---- dựng dữ liệu ----
    def add_task(self, assignees, *, title=None, end=DEADLINE, status="done", moves=(), completed_at=None,
                 deleted=False):
        """moves: danh sách (cột cũ, cột mới, người thực hiện thao tác, thời điểm) -> ghi vào activity_logs."""
        self.number += 1
        task = Task(project_id=self.project.id, number=self.number, status_id=self.st[status].id,
                    reporter_id=self.reviewer.id, title=title or f"Task {self.number}", description="d",
                    position=Decimal(self.number), start_date=min(date(2026, 11, 1), end), end_date=end,
                    completed_at=completed_at, deleted_at=at(1) if deleted else None)
        self.db.add(task)
        self.db.flush()
        for user in assignees:
            self.db.add(TaskAssignee(task_id=task.id, project_id=self.project.id, user_id=user.id))
        for old, new, actor, when in moves:
            self.db.add(ActivityLog(
                project_id=self.project.id, actor_id=actor.id if actor else None, entity_type="task",
                entity_id=task.id, action="updated", description="đổi trạng thái",
                changes={"status": {"old": old, "new": new}}, created_at=when))
        self.db.commit()
        return task

    def flow(self, worker, submit_at, returns=0, returned_by=None):
        """Luồng chuẩn: làm -> nộp -> (bị return -> nộp lại)* -> duyệt xong. Trả về (moves, thời điểm xong)."""
        returned_by = returned_by or self.reviewer
        moves = [("backlog", "in-progress", worker, submit_at - timedelta(days=2)),
                 ("in-progress", "review", worker, submit_at)]
        t = submit_at
        for _ in range(returns):
            t += timedelta(hours=1)
            moves.append(("review", "in-progress", returned_by, t))
            t += timedelta(hours=1)
            moves.append(("in-progress", "review", worker, t))
        t += timedelta(hours=1)
        moves.append(("review", "done", self.reviewer, t))
        return moves, t

    def add_done_task(self, worker, submit_at, returns=0, **kwargs):
        moves, done_at = self.flow(worker, submit_at, returns)
        return self.add_task([worker], moves=moves, completed_at=done_at, **kwargs)

    def results(self, user, **kwargs):
        """{tiêu đề task: TaskResult} của một người."""
        per_user = svc.load_task_results(self.db, self.project, **kwargs)
        return {r.title: r for r in per_user.get(user.id, [])}

    def list_api(self, user, **params):
        return self.client.get(f"/api/projects/{self.project.id}/member-evaluations",
                               headers=headers(user), params=params)

    def detail_api(self, user, target, **params):
        return self.client.get(f"/api/projects/{self.project.id}/member-evaluations/{target.id}",
                               headers=headers(user), params=params)


class ScoringTests(EvaluationFixture):
    def test_agreed_example_gives_82_5(self):
        # 5 task: 4 nộp đúng hạn, 1 trễ; số lần return lần lượt 0,1,0,2,0 -> T=80, Q=85, S=82,5
        for index, returns in enumerate([0, 1, 0, 2, 0]):
            self.add_done_task(self.alice, at(9) if index < 4 else at(12), returns=returns)
        response = self.list_api(self.reviewer)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["canViewAll"])
        self.assertEqual(body["rules"]["minTasks"], 3)
        alice = body["members"][0]
        self.assertEqual(alice["user"]["id"], str(self.alice.id))
        self.assertEqual(
            (alice["evaluatedTasks"], alice["onTimeTasks"], alice["lateTasks"], alice["returnCount"]),
            (5, 4, 1, 3))
        self.assertEqual((alice["timelinessScore"], alice["qualityScore"], alice["firstPassRate"]),
                         (80.0, 85.0, 60.0))
        self.assertEqual((alice["score"], alice["grade"], alice["gradeLabel"]), (82.5, "good", "Tốt"))
        # Người chưa có task xếp sau, theo tên: Bob rồi Zed
        self.assertEqual([m["user"]["name"] for m in body["members"]], ["Alice An", "Bob Bình", "Zed Reviewer"])
        self.assertEqual(body["members"][1]["grade"], "insufficient")

    def test_project_timezone_decides_the_day(self):
        self.add_done_task(self.alice, datetime(2026, 11, 10, 16, tzinfo=UTC), title="23h ngày hạn")
        self.add_done_task(self.alice, datetime(2026, 11, 10, 17, 30, tzinfo=UTC), title="0h30 hôm sau")
        results = self.results(self.alice)
        self.assertTrue(results["23h ngày hạn"].on_time)
        self.assertFalse(results["0h30 hôm sau"].on_time)
        self.assertEqual(results["0h30 hôm sau"].result, "late")

    def test_what_counts_as_a_return(self):
        S = self.st
        submit = ("in-progress", "review", self.alice, at(5))
        cases = {
            "người duyệt trả về": ([submit, ("review", "in-progress", self.reviewer, at(6))], 1),
            "tự rút lại": ([submit, ("review", "in-progress", self.alice, at(6))], 0),
            "Đang làm về Cần làm": ([("in-progress", "backlog", self.reviewer, at(6))], 0),
            "mở lại từ Hoàn thành": ([submit, ("review", "done", self.reviewer, at(6)),
                                      ("done", "review", self.reviewer, at(7))], 1),
            "duyệt xong (tiến lên)": ([submit, ("review", "done", self.reviewer, at(6))], 0),
            "cột tùy chỉnh theo vị trí": ([submit, ("review", "done", self.reviewer, at(6)),
                                           ("done", "testing", self.reviewer, at(7))], 1),
            "hai lần return": ([submit, ("review", "in-progress", self.reviewer, at(6)),
                                ("in-progress", "review", self.alice, at(7)),
                                ("review", "in-progress", self.reviewer, at(8))], 2),
        }
        for title, (moves, _) in cases.items():
            self.add_task([self.alice], title=title, moves=moves, completed_at=at(9))
        results = self.results(self.alice)
        for title, (_, expected) in cases.items():
            self.assertEqual(results[title].returns, expected, title)
        self.assertIn("done", S)

    def test_reviewer_delay_is_not_the_workers_fault(self):
        moves, _ = self.flow(self.alice, at(9))
        moves[-1] = ("review", "done", self.reviewer, at(15))   # duyệt chậm 6 ngày
        self.add_task([self.alice], title="duyệt chậm", moves=moves, completed_at=at(15))
        result = self.results(self.alice)["duyệt chậm"]
        self.assertTrue(result.on_time)
        self.assertEqual(svc._as_utc(result.submitted_at), at(9))

    def test_resubmitting_late_after_a_return_is_still_on_time_but_penalised(self):
        moves = [("in-progress", "review", self.alice, at(9)),
                 ("review", "in-progress", self.reviewer, at(10)),
                 ("in-progress", "review", self.alice, at(14)),
                 ("review", "done", self.reviewer, at(15))]
        self.add_task([self.alice], title="nộp lại muộn", moves=moves, completed_at=at(15))
        result = self.results(self.alice)["nộp lại muộn"]
        self.assertTrue(result.on_time)
        self.assertEqual((result.returns, result.quality), (1, 0.75))

    def test_which_tasks_are_evaluated(self):
        far_past, far_future = date(2020, 1, 1), date(2099, 1, 1)
        self.add_task([self.alice], title="quá hạn chưa nộp", status="in-progress", end=far_past)
        self.add_task([self.alice], title="quá hạn, nộp đúng hạn, chờ duyệt", status="review", end=far_past,
                      moves=[("in-progress", "review", self.alice, datetime(2019, 12, 30, 3, tzinfo=UTC))])
        self.add_task([self.alice], title="chưa tới hạn", status="in-progress", end=far_future)
        self.add_task([self.alice], title="xong sớm", end=far_future,
                      moves=self.flow(self.alice, at(9))[0], completed_at=at(10))
        self.add_task([self.alice], title="đã xóa", deleted=True, completed_at=at(9))
        self.add_task([], title="không ai làm", completed_at=at(9))
        results = self.results(self.alice)
        self.assertEqual(set(results), {"quá hạn chưa nộp", "quá hạn, nộp đúng hạn, chờ duyệt", "xong sớm"})
        self.assertEqual(results["quá hạn chưa nộp"].result, "not_submitted")
        self.assertIsNone(results["quá hạn chưa nộp"].quality)
        self.assertTrue(results["quá hạn, nộp đúng hạn, chờ duyệt"].on_time)
        self.assertTrue(results["xong sớm"].on_time)

    def test_today_can_be_injected_for_boundary(self):
        self.add_task([self.alice], title="hạn hôm nay", status="in-progress", end=date(2026, 11, 10))
        self.assertNotIn("hạn hôm nay", self.results(self.alice, today=date(2026, 11, 10)))
        self.assertIn("hạn hôm nay", self.results(self.alice, today=date(2026, 11, 11)))

    def test_old_tasks_without_logs_fall_back_to_completed_at(self):
        self.add_task([self.alice], title="cũ đúng hạn", completed_at=at(9))
        self.add_task([self.alice], title="cũ trễ", completed_at=at(12))
        results = self.results(self.alice)
        self.assertTrue(results["cũ đúng hạn"].on_time)
        self.assertEqual((results["cũ đúng hạn"].returns, results["cũ đúng hạn"].quality), (0, 1.0))
        self.assertFalse(results["cũ trễ"].on_time)

    def test_legacy_log_format_is_understood(self):
        task = self.add_task([self.alice], title="log cũ", completed_at=at(9))
        for actor, old, new, when in ((self.alice, "in-progress", "review", at(8)),
                                      (self.reviewer, "review", "in-progress", at(9))):
            self.db.add(ActivityLog(project_id=self.project.id, actor_id=actor.id, entity_type="task",
                                    entity_id=task.id, action="updated", description="x",
                                    changes={"key": "EVAL-1", "fromStatus": old, "toStatus": new},
                                    created_at=when))
        self.db.commit()
        result = self.results(self.alice)["log cũ"]
        self.assertEqual(result.returns, 1)
        self.assertEqual(svc._as_utc(result.submitted_at), at(8))

    def test_each_assignee_gets_the_full_result(self):
        moves, done = self.flow(self.alice, at(9), returns=1)
        self.add_task([self.alice, self.bob], title="chung", moves=moves, completed_at=done)
        for user in (self.alice, self.bob):
            self.assertEqual(self.results(user)["chung"].returns, 1)

    def test_return_by_a_co_assignee_is_not_counted_for_anyone(self):
        moves = [("in-progress", "review", self.alice, at(9)),
                 ("review", "in-progress", self.bob, at(10))]       # Bob cũng là người thực hiện
        self.add_task([self.alice, self.bob], title="đồng nghiệp kéo lùi", moves=moves, completed_at=at(12))
        for user in (self.alice, self.bob):
            self.assertEqual(self.results(user)["đồng nghiệp kéo lùi"].returns, 0)

    def test_unsubmitted_overdue_task_hurts_timeliness_but_not_quality(self):
        self.add_done_task(self.alice, at(9))
        self.add_done_task(self.alice, at(9))
        self.add_task([self.alice], title="bỏ dở", status="in-progress", end=date(2020, 1, 1))
        alice = self.list_api(self.reviewer).json()["members"][0]
        self.assertEqual((alice["timelinessScore"], alice["qualityScore"]), (66.7, 100.0))
        self.assertEqual((alice["score"], alice["grade"]), (83.3, "good"))
        self.assertEqual((alice["evaluatedTasks"], alice["submittedTasks"]), (3, 2))

    def test_under_three_tasks_is_insufficient_data(self):
        self.add_done_task(self.alice, at(9))
        self.add_done_task(self.alice, at(9))
        alice = self.list_api(self.reviewer).json()["members"][0]
        self.assertEqual((alice["grade"], alice["gradeLabel"], alice["score"]),
                         ("insufficient", "Chưa đủ dữ liệu", None))
        self.assertEqual(alice["timelinessScore"], 100.0)   # vẫn cho xem số liệu thành phần

    def test_grade_thresholds(self):
        for score, expected in ((100, "excellent"), (90, "excellent"), (89.9, "good"), (75, "good"),
                                (74.9, "pass"), (60, "pass"), (59.9, "needs_improvement"), (0, "needs_improvement")):
            self.assertEqual(svc.grade_for(score, 5), expected, score)
        self.assertEqual(svc.grade_for(95, 2), "insufficient")
        self.assertEqual(svc.grade_for(None, 5), "insufficient")

    def test_task_quality_never_goes_below_zero(self):
        result = svc.TaskResult(id=uuid.uuid4(), key="K-1", title="t", deadline=DEADLINE, status_code="done",
                                status_name="Xong", completed_at=at(9), submitted_at=at(9), on_time=True, returns=5)
        self.assertEqual(result.quality, 0.0)

    def test_rounding_is_half_up(self):
        self.assertEqual(svc._round1(62.25), 62.3)
        self.assertEqual(svc._round1(82.5), 82.5)
        self.assertEqual(svc._round1(66.6666), 66.7)

    def test_date_range_filters_by_deadline(self):
        self.add_done_task(self.alice, at(9, month=10), end=date(2026, 10, 10), title="tháng 10")
        self.add_done_task(self.alice, at(9), title="tháng 11")
        response = self.detail_api(self.reviewer, self.alice, **{"from": "2026-11-01", "to": "2026-11-30"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([t["title"] for t in response.json()["tasks"]], ["tháng 11"])
        self.assertEqual(self.list_api(self.reviewer, **{"from": "2026-12-01"}).json()["members"][0]["evaluatedTasks"], 0)
        self.assertEqual(self.list_api(self.reviewer, **{"from": "2026-12-01", "to": "2026-11-01"}).status_code, 400)


class AccessAndDetailTests(EvaluationFixture):
    def test_requires_login_and_membership(self):
        url = f"/api/projects/{self.project.id}/member-evaluations"
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.list_api(self.outsider).status_code, 403)

    def test_member_without_manage_permission_only_sees_self(self):
        self.add_done_task(self.alice, at(9))
        self.add_done_task(self.bob, at(9))
        body = self.list_api(self.alice).json()
        self.assertFalse(body["canViewAll"])
        self.assertEqual([m["user"]["id"] for m in body["members"]], [str(self.alice.id)])

    def test_detail_permissions(self):
        self.assertEqual(self.detail_api(self.alice, self.alice).status_code, 200)
        self.assertEqual(self.detail_api(self.alice, self.bob).status_code, 403)
        self.assertEqual(self.detail_api(self.reviewer, self.bob).status_code, 200)
        self.assertEqual(self.detail_api(self.reviewer, self.outsider).status_code, 404)
        self.assertEqual(self.detail_api(self.outsider, self.alice).status_code, 403)

    def test_detail_lists_each_task(self):
        self.add_done_task(self.alice, at(9), returns=1, title="đúng hạn, 1 return")
        self.add_done_task(self.alice, at(12), end=date(2026, 11, 20), title="hạn muộn hơn")
        self.add_task([self.alice], title="bỏ dở", status="in-progress", end=date(2020, 1, 1))
        body = self.detail_api(self.reviewer, self.alice).json()
        self.assertEqual([t["title"] for t in body["tasks"]], ["hạn muộn hơn", "đúng hạn, 1 return", "bỏ dở"])
        by_title = {t["title"]: t for t in body["tasks"]}
        first = by_title["đúng hạn, 1 return"]
        self.assertEqual((first["result"], first["returnCount"], first["qualityScore"]), ("on_time", 1, 75.0))
        self.assertTrue(first["key"].startswith("EVAL-"))
        self.assertEqual(first["deadline"], "2026-11-10")
        self.assertIsNotNone(first["submittedAt"])
        self.assertEqual(by_title["bỏ dở"]["result"], "not_submitted")
        self.assertIsNone(by_title["bỏ dở"]["submittedAt"])
        self.assertIsNone(by_title["bỏ dở"]["qualityScore"])
        self.assertEqual(body["evaluatedTasks"], 3)

    def test_unknown_project_is_rejected(self):
        response = self.client.get(f"/api/projects/{uuid.uuid4()}/member-evaluations", headers=headers(self.alice))
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
