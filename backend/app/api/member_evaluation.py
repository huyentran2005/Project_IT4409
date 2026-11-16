import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_project_permission
from app.db.session import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.evaluation import (
    EvaluationRules, MemberEvaluation, MemberEvaluationDetail, ProjectEvaluationResponse,
    TaskEvaluationItem,
)
from app.schemas.user import user_to_summary
from app.services import evaluation_service as svc

router = APIRouter(prefix="/projects", tags=["member-evaluation"])


def _get_project(db: Session, project_id: uuid.UUID) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy dự án")
    return project


def _check_range(date_from: date | None, date_to: date | None) -> None:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày bắt đầu không được sau ngày kết thúc.",
        )


def _member_response(user: User, summary: svc.MemberSummary) -> MemberEvaluation:
    return MemberEvaluation(
        user=user_to_summary(user),
        evaluatedTasks=summary.evaluated, submittedTasks=summary.submitted,
        onTimeTasks=summary.on_time, lateTasks=summary.late, returnCount=summary.returns,
        firstPassRate=summary.first_pass_rate, timelinessScore=summary.timeliness,
        qualityScore=summary.quality, score=summary.score,
        grade=summary.grade, gradeLabel=svc.GRADE_LABELS[summary.grade],
    )


def _rules() -> EvaluationRules:
    return EvaluationRules(
        minTasks=svc.MIN_EVALUATED_TASKS, returnPenalty=svc.RETURN_PENALTY,
        timelinessWeight=svc.TIMELINESS_WEIGHT, qualityWeight=svc.QUALITY_WEIGHT,
        thresholds={grade: threshold for grade, threshold in svc.GRADE_THRESHOLDS},
    )


@router.get("/{project_id}/member-evaluations", response_model=ProjectEvaluationResponse)
def get_member_evaluations(
    project_id: uuid.UUID,
    caller: Annotated[ProjectMember, Depends(require_project_permission("project.view"))],
    db: Annotated[Session, Depends(get_db)],
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
):
    """
    Đánh giá mức độ hoàn thành công việc của từng thành viên trong dự án.

    Input: Header Authorization Bearer; query tùy chọn `from`, `to` (YYYY-MM-DD, lọc theo ngày kết thúc task).
    Output: 200 {canViewAll, rules, members[]}. Người có quyền `member.manage` xem cả nhóm,
        người khác chỉ thấy điểm của chính mình. 400 nếu from > to; 401 chưa đăng nhập;
        403 không phải thành viên dự án; 404 dự án không tồn tại.
    Điểm: 50% đúng hạn (lần nộp đầu <= ngày kết thúc) + 50% chất lượng (mỗi lần bị return trừ 25% điểm task).
    """
    _check_range(date_from, date_to)
    project = _get_project(db, project_id)
    can_view_all = svc.has_project_permission(db, project.id, caller.user_id, "member.manage")

    per_user = svc.load_task_results(db, project, date_from, date_to)
    members = svc.project_members(db, project)
    if not can_view_all:
        members = [member for member in members if member.id == caller.user_id]

    items = [(member, svc.summarize(per_user.get(member.id, []))) for member in members]
    # Người đủ dữ liệu xếp trước theo điểm giảm dần; người chưa đủ dữ liệu xếp sau theo tên.
    items.sort(key=lambda pair: (pair[1].score is None, -(pair[1].score or 0), pair[0].full_name))
    return ProjectEvaluationResponse(
        projectId=str(project.id), dateFrom=date_from, dateTo=date_to, canViewAll=can_view_all,
        rules=_rules(), members=[_member_response(user, summary) for user, summary in items],
    )


@router.get("/{project_id}/member-evaluations/{user_id}", response_model=MemberEvaluationDetail)
def get_member_evaluation_detail(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    caller: Annotated[ProjectMember, Depends(require_project_permission("project.view"))],
    db: Annotated[Session, Depends(get_db)],
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
):
    """
    Chi tiết đánh giá của một thành viên: điểm tổng hợp và kết quả từng task.

    Input: như API danh sách; `user_id` là người được xem.
    Output: 200 MemberEvaluationDetail; 403 nếu xem người khác mà không có quyền `member.manage`;
        404 nếu người đó không phải thành viên dự án.
    """
    _check_range(date_from, date_to)
    project = _get_project(db, project_id)
    if user_id != caller.user_id and not svc.has_project_permission(
            db, project.id, caller.user_id, "member.manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn chỉ được xem đánh giá của chính mình.",
        )
    user = next((member for member in svc.project_members(db, project) if member.id == user_id), None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thành viên trong dự án")

    results = svc.load_task_results(db, project, date_from, date_to).get(user_id, [])
    results.sort(key=lambda r: (r.deadline, r.key), reverse=True)
    base = _member_response(user, svc.summarize(results))
    return MemberEvaluationDetail(
        **base.model_dump(),
        tasks=[
            TaskEvaluationItem(
                id=str(r.id), key=r.key, title=r.title, deadline=r.deadline,
                status=r.status_code, statusName=r.status_name,
                submittedAt=svc._as_utc(r.submitted_at) if r.submitted_at else None,
                completedAt=svc._as_utc(r.completed_at) if r.completed_at else None,
                result=r.result, returnCount=r.returns,
                qualityScore=round(r.quality * 100, 1) if r.quality is not None else None,
            )
            for r in results
        ],
    )
