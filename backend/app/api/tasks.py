import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.task import (
    BoardDataResponse,
    CreateTaskRequest,
    MoveTaskRequest,
    SetReviewerRequest,
    TaskResponse,
    UpdateTaskPropertiesRequest,
)
from app.services.task_service import (
    TaskServiceError,
    create_task,
    delete_task,
    get_project_board,
    list_all_user_tasks,
    list_project_tasks,
    move_task,
    resolve_project_id,
    set_task_reviewer,
    update_task_properties,
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
    "/tasks",
    response_model=list[TaskResponse],
)
def read_all_user_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lấy danh sách tất cả các công việc (chưa xóa) thuộc mọi dự án mà người dùng hiện tại tham gia.

    Input (Đầu vào):
        - Authorization Header: Bearer <access_token>.

    Output (Đầu ra):
        - 200 OK: Danh sách list[TaskResponse] của toàn bộ công việc trên tất cả dự án để thống kê tổng hợp.
        - 401 Unauthorized: Chưa đăng nhập hoặc token hết hạn.
    """
    return list_all_user_tasks(db, current_user=current_user)


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

    Input (Đầu vào):
        - project_id (UUID hoặc mã mặc định 'p-01', path param): Định danh dự án.
        - Authorization Header: Bearer <access_token>.

    Output (Đầu ra):
        - 200 OK: Đối tượng BoardDataResponse (project summary + danh sách 4 cột kèm các task chưa xóa).
        - 401 Unauthorized: Chưa đăng nhập hoặc token hết hạn.
        - 403 Forbidden: Người dùng không phải là thành viên của dự án.
        - 404 Not Found: Không tìm thấy dự án hoặc người dùng chưa có dự án nào.
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

    Input (Đầu vào):
        - project_id (UUID hoặc mã mặc định 'p-01', path param): Định danh dự án.
        - Authorization Header: Bearer <access_token>.

    Output (Đầu ra):
        - 200 OK: Danh sách list[TaskResponse] của toàn bộ công việc chưa xóa trong dự án.
        - 401 Unauthorized: Chưa đăng nhập hoặc token hết hạn.
        - 403 Forbidden: Người dùng không phải là thành viên của dự án.
        - 404 Not Found: Không tìm thấy dự án.
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


@router.patch(
    "/tasks/{task_id}/move",
    response_model=TaskResponse,
)
def move_project_task(
    task_id: uuid.UUID,
    payload: MoveTaskRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Di chuyển công việc sang cột trạng thái mới (kéo-thả trên Kanban hoặc đổi trong Drawer).

    Input (Đầu vào):
        - task_id (UUID, path param): Định danh công việc cần di chuyển.
        - payload (MoveTaskRequest, JSON body): Trạng thái đích `status`, `position` và tùy chọn `reviewerId`, các thuộc tính công việc.
        - Authorization Header: Bearer <access_token>.

    Output (Đầu ra):
        - 200 OK: Đối tượng TaskResponse sau khi đã cập nhật trạng thái, vị trí và `completedAt`.
        - 400 Bad Request: Trạng thái không tồn tại, vượt WIP limit, thiếu `reviewerId` khi sang `review`, hoặc dữ liệu không hợp lệ.
        - 401 Unauthorized: Chưa đăng nhập hoặc token hết hạn.
        - 403 Forbidden: Không thuộc dự án hoặc không có quyền `task.manage`.
        - 404 Not Found: Không tìm thấy công việc hoặc công việc đã bị xóa.
    """
    client_ip = request.client.host if request.client else None
    try:
        return move_task(
            db,
            task_id=task_id,
            current_user=current_user,
            payload=payload,
            client_ip=client_ip,
        )
    except TaskServiceError as exc:
        _raise_http_error(exc)


@router.patch(
    "/tasks/{task_id}/reviewer",
    response_model=TaskResponse,
)
def update_task_reviewer_endpoint(
    task_id: uuid.UUID,
    payload: SetReviewerRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cập nhật người duyệt (reviewer) cho công việc.

    Input (Đầu vào):
        - task_id (UUID, path param): Định danh công việc cần gán người duyệt.
        - payload (SetReviewerRequest, JSON body): `{ reviewerId: UUID }` của thành viên duyệt.
        - Authorization Header: Bearer <access_token>.

    Output (Đầu ra):
        - 200 OK: Đối tượng TaskResponse đã cập nhật thông tin `reviewer`.
        - 400 Bad Request: `reviewerId` không phải là thành viên hợp lệ của dự án.
        - 401 Unauthorized: Chưa đăng nhập hoặc token hết hạn.
        - 403 Forbidden: Không có quyền `task.manage` trong dự án.
        - 404 Not Found: Không tìm thấy công việc hoặc công việc đã bị xóa.
    """
    client_ip = request.client.host if request.client else None
    try:
        return set_task_reviewer(
            db,
            task_id=task_id,
            current_user=current_user,
            payload=payload,
            client_ip=client_ip,
        )
    except TaskServiceError as exc:
        _raise_http_error(exc)


@router.patch(
    "/tasks/{task_id}/properties",
    response_model=TaskResponse,
)
def update_task_properties_endpoint(
    task_id: uuid.UUID,
    payload: UpdateTaskPropertiesRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cập nhật các thuộc tính chi tiết của công việc trong TaskDrawer.

    Input (Đầu vào):
        - task_id (UUID, path param): Định danh công việc cần cập nhật.
        - payload (UpdateTaskPropertiesRequest, JSON body): `{ description, priority, assigneeIds, startDate, endDate, overdueReason, acceptanceResult }`.
        - Authorization Header: Bearer <access_token>.

    Output (Đầu ra):
        - 200 OK: Đối tượng TaskResponse sau khi cập nhật thuộc tính và danh sách người thực hiện.
        - 400 Bad Request: Một hoặc nhiều `assigneeIds` không thuộc dự án.
        - 401 Unauthorized: Chưa đăng nhập hoặc token hết hạn.
        - 403 Forbidden: Không có quyền `task.manage` trong dự án.
        - 404 Not Found: Không tìm thấy công việc hoặc công việc đã bị xóa.
        - 422 Unprocessable Entity: Dữ liệu đầu vào không hợp lệ (ví dụ `endDate < startDate` hoặc `description` rỗng).
    """
    client_ip = request.client.host if request.client else None
    try:
        return update_task_properties(
            db,
            task_id=task_id,
            current_user=current_user,
            payload=payload,
            client_ip=client_ip,
        )
    except TaskServiceError as exc:
        _raise_http_error(exc)
