import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.task import BoardDataResponse, CreateTaskRequest, TaskResponse
from app.services.task_service import (
    TaskServiceError,
    create_task,
    delete_task,
    get_project_board,
    list_project_tasks,
    resolve_project_id,
)

router = APIRouter(tags=["tasks"])

_ERROR_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "forbidden": status.HTTP_403_FORBIDDEN,
    "bad_request": status.HTTP_400_BAD_REQUEST,
    "conflict": status.HTTP_409_CONFLICT,
}


def _raise_http_error(exc: TaskServiceError) -> None:
    http_status = _ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST)
    raise HTTPException(status_code=http_status, detail=exc.message)


@router.get(
    "/projects/{project_id}/board",
    response_model=BoardDataResponse,
)
def read_project_board(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lấy dữ liệu bảng Kanban của dự án (thông tin dự án, thành viên, các cột trạng thái và danh sách công việc).
    Nếu người dùng chưa có dự án nào và truyền mã mặc định 'p-01', hệ thống tự động khởi tạo dự án mặc định.
    """
    try:
        return get_project_board(
            db,
            project_id_or_alias=project_id,
            current_user=current_user,
        )
    except TaskServiceError as exc:
        _raise_http_error(exc)


@router.get(
    "/projects/{project_id}/tasks",
    response_model=list[TaskResponse],
)
def read_project_tasks(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lấy danh sách tất cả các công việc (chưa xóa) của dự án.
    """
    try:
        return list_project_tasks(
            db,
            project_id_or_alias=project_id,
            current_user=current_user,
        )
    except TaskServiceError as exc:
        _raise_http_error(exc)


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_task(
    project_id: str,
    payload: CreateTaskRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Tạo một công việc mới trong dự án.

    Input (Đầu vào):
        - project_id (UUID hoặc mã mặc định 'p-01', path param): Định danh dự án.
        - payload (CreateTaskRequest, JSON body): Thông tin công việc (title, description, type, priority, startDate, endDate, assigneeIds, status).
        - Authorization Header: Bearer <access_token>.

    Output (Đầu ra):
        - 201 Created: Đối tượng TaskResponse khớp định dạng với Frontend.
        - 400 Bad Request: Trạng thái không tồn tại, vượt WIP limit hoặc assignee không hợp lệ.
        - 401 Unauthorized: Chưa đăng nhập hoặc token hết hạn.
        - 403 Forbidden: Không thuộc dự án hoặc không có quyền `task.manage`.
        - 404 Not Found: Không tìm thấy dự án.
    """
    client_ip = request.client.host if request.client else None
    try:
        resolved_pid = resolve_project_id(db, project_id, current_user)
        return create_task(
            db,
            project_id=resolved_pid,
            current_user=current_user,
            payload=payload,
            client_ip=client_ip,
        )
    except TaskServiceError as exc:
        _raise_http_error(exc)


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_task(
    task_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Xóa mềm một công việc (cập nhật cột `deleted_at`).

    Input (Đầu vào):
        - task_id (UUID, path param): Định danh công việc cần xóa.
        - Authorization Header: Bearer <access_token>.

    Output (Đầu ra):
        - 204 No Content: Xóa thành công.
        - 401 Unauthorized: Chưa đăng nhập hoặc token hết hạn.
        - 403 Forbidden: Không có quyền `task.manage` trong dự án chứa công việc.
        - 404 Not Found: Không tìm thấy công việc hoặc công việc đã bị xóa trước đó.
    """
    client_ip = request.client.host if request.client else None
    try:
        delete_task(
            db,
            task_id=task_id,
            current_user=current_user,
            client_ip=client_ip,
        )
    except TaskServiceError as exc:
        _raise_http_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
