import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import func, update
from sqlalchemy.orm import Session, joinedload
from app.models.user import User
from app.models.project import Project, Status
from app.models.project_role import Permission, ProjectRole, ProjectRolePermission
from app.models.project_member import ProjectMember
from app.models.task import Task, TaskAssignee, ActivityLog
from app.schemas.task import (
    BoardColumnResponse,
    BoardDataResponse,
    CreateTaskRequest,
    MoveTaskRequest,
    ProjectSummaryResponse,
    SetReviewerRequest,
    TaskResponse,
    UpdateTaskPropertiesRequest,
    task_to_response,
)
from app.schemas.user import user_to_summary
from app.services.auth_service import sanitize_ip


class TaskServiceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def resolve_project_id(
    db: Session, project_id_or_alias: str, user: User
) -> uuid.UUID:
    """
    Chuyển chuỗi project_id trên URL thành UUID thực tế.
    Nếu truyền mã mặc định (như 'p-01'), trả về dự án đầu tiên mà user là thành viên.

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - project_id_or_alias (str): Chuỗi UUID dự án hoặc mã giả định ('p-01').
        - user (User): Người dùng hiện tại.

    Output (Đầu ra):
        - uuid.UUID: Định danh UUID thực tế của dự án.
        - Raise TaskServiceError ('not_found') nếu không tìm thấy dự án.
    """
    try:
        return uuid.UUID(project_id_or_alias)
    except (ValueError, TypeError):
        existing = (
            db.query(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .filter(
                ProjectMember.user_id == user.id,
                Project.deleted_at.is_(None),
            )
            .order_by(Project.created_at.asc())
            .first()
        )
        if not existing:
            raise TaskServiceError("not_found", "Không tìm thấy dự án.")
        return existing.id


def check_task_manage_permission(
    db: Session, project_id: uuid.UUID, user_id: uuid.UUID
) -> Project:
    """
    Kiểm tra dự án tồn tại, chưa bị xóa/lưu trữ và người dùng hiện tại
    là thành viên có quyền 'task.manage' trong dự án.

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - project_id (UUID): Định danh dự án.
        - user_id (UUID): Định danh người dùng cần kiểm tra quyền.

    Output (Đầu ra):
        - Project: Bản ghi dự án hợp lệ.
        - Raise TaskServiceError ('not_found', 'bad_request', 'forbidden') nếu không hợp lệ.
    """
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        raise TaskServiceError("not_found", "Không tìm thấy dự án.")

    if project.is_archived:
        raise TaskServiceError(
            "bad_request",
            "Dự án đã được lưu trữ, không thể tạo hoặc xóa công việc.",
        )

    member = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        .first()
    )
    if not member:
        raise TaskServiceError(
            "forbidden", "Bạn không phải là thành viên của dự án này."
        )

    # Chủ sở hữu dự án luôn có toàn quyền
    if project.owner_id == user_id:
        return project

    role = db.query(ProjectRole).filter(ProjectRole.id == member.role_id).first()
    if role and role.code == "owner":
        return project

    # Kiểm tra bảng phân quyền project_role_permissions
    has_explicit_perm = (
        db.query(ProjectRolePermission)
        .join(Permission, Permission.id == ProjectRolePermission.permission_id)
        .filter(
            ProjectRolePermission.role_id == member.role_id,
            Permission.code == "task.manage",
        )
        .first()
        is not None
    )
    if has_explicit_perm:
        return project

    # Nếu role này chưa được cấu hình dòng nào trong project_role_permissions
    # thì áp dụng ma trận quyền mặc định (owner, manager, member có quyền; viewer không có quyền)
    any_perm_configured = (
        db.query(ProjectRolePermission)
        .filter(ProjectRolePermission.role_id == member.role_id)
        .first()
        is not None
    )
    if not any_perm_configured and role and role.code in ("owner", "manager", "member"):
        return project

    raise TaskServiceError(
        "forbidden",
        "Bạn không có quyền quản lý công việc (task.manage) trong dự án này.",
    )


def get_project_board(
    db: Session,
    *,
    project_id_or_alias: str,
    current_user: User,
) -> BoardDataResponse:
    """
    Trả về dữ liệu Board (ProjectSummary + danh sách cột kèm các Task chưa xóa)
    để hiển thị trực tiếp trên giao diện Kanban của Frontend.

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - project_id_or_alias (str): Chuỗi UUID dự án hoặc mã giả định ('p-01').
        - current_user (User): Người dùng đang đăng nhập.

    Output (Đầu ra):
        - BoardDataResponse: Thông tin dự án, thành viên, tiến độ % và danh sách các cột kèm công việc.
        - Raise TaskServiceError ('not_found', 'forbidden') nếu không tìm thấy hoặc không thuộc dự án.
    """
    project_id = resolve_project_id(db, project_id_or_alias, current_user)
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.deleted_at.is_(None))
        .first()
    )
    if not project:
        raise TaskServiceError("not_found", "Không tìm thấy dự án.")

    is_member = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        )
        .first()
        is not None
    )
    if not is_member and project.owner_id != current_user.id:
        raise TaskServiceError(
            "forbidden", "Bạn không phải là thành viên của dự án này."
        )

    statuses = (
        db.query(Status)
        .filter(Status.project_id == project_id)
        .order_by(Status.position.asc())
        .all()
    )

    tasks = (
        db.query(Task)
        .options(
            joinedload(Task.assignee_links).joinedload(TaskAssignee.user),
            joinedload(Task.reviewer),
        )
        .filter(
            Task.project_id == project_id,
            Task.deleted_at.is_(None),
        )
        .order_by(Task.position.asc(), Task.created_at.desc())
        .all()
    )

    member_users = (
        db.query(User)
        .join(
            ProjectMember,
            (ProjectMember.user_id == User.id)
            & (ProjectMember.project_id == project_id),
        )
        .filter(User.deleted_at.is_(None))
        .order_by(ProjectMember.joined_at.asc())
        .all()
    )

    status_by_id = {s.id: s for s in statuses}
    tasks_by_status: dict[uuid.UUID, list[TaskResponse]] = {s.id: [] for s in statuses}
    done_count = 0

    for t in tasks:
        st = status_by_id.get(t.status_id)
        if not st:
            continue
        if st.category == "done":
            done_count += 1
        tasks_by_status[st.id].append(
            task_to_response(t, project_key=project.key, status_code=st.code)
        )

    total_tasks = sum(len(items) for items in tasks_by_status.values())
    progress = round((done_count / total_tasks) * 100) if total_tasks > 0 else 0

    columns = [
        BoardColumnResponse(
            id=s.code,
            title=s.name,
            accent=s.color,
            limit=s.wip_limit,
            tasks=tasks_by_status.get(s.id, []),
        )
        for s in statuses
    ]

    return BoardDataResponse(
        project=ProjectSummaryResponse(
            id=str(project.id),
            key=project.key.upper(),
            name=project.name,
            description=project.description,
            color=project.color,
            progress=progress,
            totalTasks=total_tasks,
            doneTasks=done_count,
            members=[user_to_summary(u) for u in member_users],
        ),
        columns=columns,
    )


def list_all_user_tasks(
    db: Session,
    *,
    current_user: User,
) -> list[TaskResponse]:
    """
    Lấy toàn bộ danh sách công việc (chưa xóa) thuộc tất cả các dự án mà người dùng hiện tại tham gia.

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - current_user (User): Người dùng đang đăng nhập.

    Output (Đầu ra):
        - list[TaskResponse]: Danh sách toàn bộ công việc chưa xóa trên tất cả dự án của người dùng.
    """
    tasks = (
        db.query(Task)
        .join(Project, Project.id == Task.project_id)
        .join(
            ProjectMember,
            (ProjectMember.project_id == Project.id)
            & (ProjectMember.user_id == current_user.id),
        )
        .options(
            joinedload(Task.project),
            joinedload(Task.status),
            joinedload(Task.assignee_links).joinedload(TaskAssignee.user),
            joinedload(Task.reviewer),
        )
        .filter(
            Project.deleted_at.is_(None),
            Task.deleted_at.is_(None),
        )
        .order_by(Task.created_at.desc())
        .all()
    )
    return [task_to_response(t) for t in tasks]


def list_project_tasks(
    db: Session,
    *,
    project_id_or_alias: str,
    current_user: User,
) -> list[TaskResponse]:
    """
    Lấy danh sách phẳng toàn bộ các công việc chưa xóa của dự án.

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - project_id_or_alias (str): Chuỗi UUID dự án hoặc mã giả định ('p-01').
        - current_user (User): Người dùng đang đăng nhập.

    Output (Đầu ra):
        - list[TaskResponse]: Danh sách tất cả công việc chưa xóa của dự án.
    """
    board = get_project_board(
        db,
        project_id_or_alias=project_id_or_alias,
        current_user=current_user,
    )
    return [task for col in board.columns for task in col.tasks]


def _compute_new_task_position(
    db: Session, project_id: uuid.UUID, status_id: uuid.UUID
) -> Decimal:
    """
    Tính toán vị trí (position) cho task mới để đặt ở đầu cột trạng thái.

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - project_id (UUID): Định danh dự án.
        - status_id (UUID): Định danh cột trạng thái.

    Output (Đầu ra):
        - Decimal: Giá trị position mới nhỏ hơn position nhỏ nhất hiện tại trong cột.
    """
    min_position = (
        db.query(func.min(Task.position))
        .filter(
            Task.project_id == project_id,
            Task.status_id == status_id,
            Task.deleted_at.is_(None),
        )
        .scalar()
    )
    if min_position is None:
        return Decimal("1000")
    min_dec = Decimal(str(min_position))
    if min_dec > Decimal("1"):
        return min_dec - Decimal("1")
    return min_dec / Decimal("2")


def create_task(
    db: Session,
    *,
    project_id: uuid.UUID,
    current_user: User,
    payload: CreateTaskRequest,
    client_ip: str | None = None,
) -> TaskResponse:
    """
    Tạo công việc mới trong dự án.

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - project_id (UUID): Định danh dự án.
        - current_user (User): Người dùng tạo công việc (reporter).
        - payload (CreateTaskRequest): Dữ liệu công việc cần tạo (`title`, `description`, `type`, `priority`, `startDate`, `endDate`, `assigneeIds`, `status`).
        - client_ip (str | None): Địa chỉ IP của client để ghi nhận ActivityLog.

    Output (Đầu ra):
        - TaskResponse: Đối tượng công việc vừa tạo.
        - Raise TaskServiceError ('not_found', 'forbidden', 'bad_request') nếu không hợp lệ.
    """
    project = check_task_manage_permission(db, project_id, current_user.id)

    status_obj = (
        db.query(Status)
        .filter(
            Status.project_id == project_id,
            Status.code == payload.status,
        )
        .first()
    )
    if not status_obj:
        raise TaskServiceError(
            "bad_request",
            f"Trạng thái '{payload.status}' không tồn tại trong dự án này.",
        )

    if status_obj.wip_limit is not None:
        current_count = (
            db.query(func.count(Task.id))
            .filter(
                Task.project_id == project_id,
                Task.status_id == status_obj.id,
                Task.deleted_at.is_(None),
            )
            .scalar()
            or 0
        )
        if current_count >= status_obj.wip_limit:
            raise TaskServiceError(
                "bad_request",
                f"Cột '{status_obj.name}' đã đạt giới hạn công việc tối đa ({status_obj.wip_limit}).",
            )

    assignee_users: list[User] = []
    if payload.assigneeIds:
        rows = (
            db.query(User)
            .join(
                ProjectMember,
                (ProjectMember.user_id == User.id)
                & (ProjectMember.project_id == project_id),
            )
            .filter(
                User.id.in_(payload.assigneeIds),
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
            .all()
        )
        users_by_id = {u.id: u for u in rows}
        missing = [uid for uid in payload.assigneeIds if uid not in users_by_id]
        if missing:
            raise TaskServiceError(
                "bad_request",
                "Một hoặc nhiều người được giao việc không phải là thành viên hợp lệ của dự án.",
            )
        assignee_users = [users_by_id[uid] for uid in payload.assigneeIds]

    # Tăng task_sequence nguyên tử để tránh trùng số thứ tự khi gọi đồng thời
    seq_stmt = (
        update(Project)
        .where(Project.id == project_id)
        .values(task_sequence=Project.task_sequence + 1)
        .returning(Project.task_sequence)
    )
    task_number = int(db.execute(seq_stmt).scalar_one())

    position = _compute_new_task_position(db, project_id, status_obj.id)
    now = datetime.now(timezone.utc)
    completed_at = now if status_obj.category == "done" else None

    task = Task(
        project_id=project_id,
        number=task_number,
        status_id=status_obj.id,
        reporter_id=current_user.id,
        type=payload.type,
        priority=payload.priority,
        title=payload.title,
        description=payload.description,
        position=position,
        start_date=payload.startDate,
        end_date=payload.endDate,
        completed_at=completed_at,
    )
    db.add(task)
    db.flush()

    for assignee in assignee_users:
        link = TaskAssignee(
            task_id=task.id,
            project_id=project_id,
            user_id=assignee.id,
        )
        link.user = assignee
        task.assignee_links.append(link)

    task_key = f"{project.key.upper()}-{task_number}"
    log_entry = ActivityLog(
        project_id=project_id,
        actor_id=current_user.id,
        entity_type="task",
        entity_id=task.id,
        action="created",
        description=f"Đã tạo công việc {task_key}: {task.title}",
        changes={
            "key": task_key,
            "title": task.title,
            "type": task.type,
            "priority": task.priority,
            "status": status_obj.code,
            "startDate": payload.startDate.isoformat(),
            "endDate": payload.endDate.isoformat(),
            "assigneeIds": [str(u.id) for u in assignee_users],
        },
        ip_address=sanitize_ip(client_ip),
    )
    db.add(log_entry)

    db.commit()
    db.refresh(task)

    return task_to_response(
        task,
        project_key=project.key,
        status_code=status_obj.code,
    )


def delete_task(
    db: Session,
    *,
    task_id: uuid.UUID,
    current_user: User,
    client_ip: str | None = None,
) -> None:
    """
    Xóa mềm công việc (gán tasks.deleted_at = now()).

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - task_id (UUID): Định danh công việc cần xóa.
        - current_user (User): Người dùng thực hiện xóa.
        - client_ip (str | None): Địa chỉ IP của client để ghi nhận ActivityLog.

    Output (Đầu ra):
        - None (Cập nhật `deleted_at` và lưu `ActivityLog`).
        - Raise TaskServiceError ('not_found', 'forbidden') nếu không tìm thấy hoặc không đủ quyền.
    """
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.deleted_at.is_(None))
        .first()
    )
    if not task:
        raise TaskServiceError(
            "not_found", "Không tìm thấy công việc hoặc công việc đã bị xóa."
        )

    project = check_task_manage_permission(db, task.project_id, current_user.id)

    now = datetime.now(timezone.utc)
    task.deleted_at = now

    task_key = f"{project.key.upper()}-{task.number}"
    log_entry = ActivityLog(
        project_id=task.project_id,
        actor_id=current_user.id,
        entity_type="task",
        entity_id=task.id,
        action="deleted",
        description=f"Đã xóa công việc {task_key}: {task.title}",
        changes={
            "key": task_key,
            "title": task.title,
            "deletedAt": now.isoformat(),
        },
        ip_address=sanitize_ip(client_ip),
    )
    db.add(log_entry)

    db.commit()


def _compute_end_task_position(
    db: Session,
    project_id: uuid.UUID,
    status_id: uuid.UUID,
    exclude_task_id: uuid.UUID | None = None,
) -> Decimal:
    """
    Tính toán vị trí (position) cho task được kéo thả sang cột mới (đặt ở cuối cột).

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - project_id (UUID): Định danh dự án.
        - status_id (UUID): Định danh cột trạng thái đích.
        - exclude_task_id (UUID | None): ID của task đang di chuyển để loại trừ khi tính max.

    Output (Đầu ra):
        - Decimal: Giá trị position mới ở cuối cột trạng thái đích.
    """
    query = db.query(func.max(Task.position)).filter(
        Task.project_id == project_id,
        Task.status_id == status_id,
        Task.deleted_at.is_(None),
    )
    if exclude_task_id is not None:
        query = query.filter(Task.id != exclude_task_id)
    max_position = query.scalar()
    if max_position is None:
        return Decimal("1000")
    return Decimal(str(max_position)) + Decimal("1000")


def _resolve_project_member_users(
    db: Session, project_id: uuid.UUID, user_ids: list[uuid.UUID]
) -> list[User]:
    """
    Kiểm tra và trả về danh sách bản ghi User thuộc dự án theo danh sách ID.

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - project_id (UUID): Định danh dự án.
        - user_ids (list[UUID]): Danh sách ID người dùng cần kiểm tra.

    Output (Đầu ra):
        - list[User]: Danh sách đối tượng User hợp lệ theo đúng thứ tự `user_ids`.
        - Raise TaskServiceError ('bad_request') nếu có user không thuộc dự án.
    """
    if not user_ids:
        return []
    rows = (
        db.query(User)
        .join(
            ProjectMember,
            (ProjectMember.user_id == User.id)
            & (ProjectMember.project_id == project_id),
        )
        .filter(
            User.id.in_(user_ids),
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
        .all()
    )
    users_by_id = {u.id: u for u in rows}
    missing = [uid for uid in user_ids if uid not in users_by_id]
    if missing:
        raise TaskServiceError(
            "bad_request",
            "Một hoặc nhiều người được chọn không phải là thành viên hợp lệ của dự án.",
        )
    return [users_by_id[uid] for uid in user_ids]


def move_task(
    db: Session,
    *,
    task_id: uuid.UUID,
    current_user: User,
    payload: MoveTaskRequest,
    client_ip: str | None = None,
) -> TaskResponse:
    """
    Di chuyển công việc sang cột trạng thái mới (kéo-thả trên Kanban hoặc đổi trong Drawer).

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - task_id (UUID): Định danh công việc cần di chuyển.
        - current_user (User): Người dùng đang thực hiện thao tác.
        - payload (MoveTaskRequest): Trạng thái đích `status`, `position` và tùy chọn `reviewerId`, các thuộc tính công việc.
        - client_ip (str | None): Địa chỉ IP của client để ghi nhận ActivityLog.

    Output (Đầu ra):
        - TaskResponse: Thông tin công việc sau khi cập nhật trạng thái, vị trí và `completedAt`.
        - Raise TaskServiceError ('not_found', 'forbidden', 'bad_request') nếu vi phạm quyền hoặc điều kiện nghiệp vụ.
    """
    task = (
        db.query(Task)
        .options(
            joinedload(Task.assignee_links).joinedload(TaskAssignee.user),
            joinedload(Task.reviewer),
            joinedload(Task.status),
        )
        .filter(Task.id == task_id, Task.deleted_at.is_(None))
        .first()
    )
    if not task:
        raise TaskServiceError(
            "not_found", "Không tìm thấy công việc hoặc công việc đã bị xóa."
        )

    project = check_task_manage_permission(db, task.project_id, current_user.id)

    status_obj = (
        db.query(Status)
        .filter(
            Status.project_id == task.project_id,
            Status.code == payload.status,
        )
        .first()
    )
    if not status_obj:
        raise TaskServiceError(
            "bad_request",
            f"Trạng thái '{payload.status}' không tồn tại trong dự án này.",
        )

    if status_obj.id != task.status_id and status_obj.wip_limit is not None:
        current_count = (
            db.query(func.count(Task.id))
            .filter(
                Task.project_id == task.project_id,
                Task.status_id == status_obj.id,
                Task.deleted_at.is_(None),
                Task.id != task.id,
            )
            .scalar()
            or 0
        )
        if current_count >= status_obj.wip_limit:
            raise TaskServiceError(
                "bad_request",
                f"Cột '{status_obj.name}' đã đạt giới hạn công việc tối đa ({status_obj.wip_limit}).",
            )

    if payload.reviewerId is not None:
        reviewer_user = _resolve_project_member_users(
            db, task.project_id, [payload.reviewerId]
        )[0]
        task.reviewer_id = reviewer_user.id
        task.reviewer = reviewer_user

    if payload.description is not None:
        cleaned_desc = payload.description.strip()
        if not cleaned_desc:
            raise TaskServiceError(
                "bad_request", "Mô tả công việc không được để trống."
            )
        task.description = cleaned_desc

    if payload.priority is not None:
        task.priority = payload.priority

    if payload.startDate is not None:
        task.start_date = payload.startDate
    if payload.endDate is not None:
        task.end_date = payload.endDate
    if task.end_date < task.start_date:
        raise TaskServiceError(
            "bad_request", "Ngày kết thúc không được trước ngày bắt đầu."
        )

    if payload.overdueReason is not None:
        task.overdue_reason = payload.overdueReason.strip() or None

    if payload.acceptanceResult is not None:
        task.acceptance_result = payload.acceptanceResult.strip() or None

    if payload.assigneeIds is not None:
        assignee_users = _resolve_project_member_users(
            db, task.project_id, payload.assigneeIds
        )
        task.assignee_links.clear()
        db.flush()
        for assignee in assignee_users:
            link = TaskAssignee(
                task_id=task.id,
                project_id=task.project_id,
                user_id=assignee.id,
            )
            link.user = assignee
            task.assignee_links.append(link)

    if status_obj.code == "review" and task.reviewer_id is None:
        raise TaskServiceError(
            "bad_request",
            "Cần chọn người duyệt trước khi chuyển sang trạng thái Đang duyệt.",
        )

    old_status_code = task.status.code if task.status else None
    now = datetime.now(timezone.utc)

    if status_obj.id != task.status_id:
        task.position = _compute_end_task_position(
            db, task.project_id, status_obj.id, exclude_task_id=task.id
        )
        task.status_id = status_obj.id
        task.status = status_obj

    if status_obj.category == "done":
        if task.completed_at is None:
            task.completed_at = now
    else:
        task.completed_at = None

    task_key = f"{project.key.upper()}-{task.number}"
    log_entry = ActivityLog(
        project_id=task.project_id,
        actor_id=current_user.id,
        entity_type="task",
        entity_id=task.id,
        action="updated",
        description=f"Đã chuyển công việc {task_key} sang trạng thái {status_obj.name}",
        changes={
            "key": task_key,
            "fromStatus": old_status_code,
            "toStatus": status_obj.code,
            "reviewerId": str(task.reviewer_id) if task.reviewer_id else None,
        },
        ip_address=sanitize_ip(client_ip),
    )
    db.add(log_entry)

    db.commit()
    db.refresh(task)

    return task_to_response(
        task,
        project_key=project.key,
        status_code=status_obj.code,
    )


def set_task_reviewer(
    db: Session,
    *,
    task_id: uuid.UUID,
    current_user: User,
    payload: SetReviewerRequest,
    client_ip: str | None = None,
) -> TaskResponse:
    """
    Cập nhật người duyệt (reviewer) cho công việc.

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - task_id (UUID): Định danh công việc cần cập nhật người duyệt.
        - current_user (User): Người dùng đang thực hiện thao tác.
        - payload (SetReviewerRequest): Chứa `reviewerId` (UUID của thành viên duyệt).
        - client_ip (str | None): Địa chỉ IP của client để ghi nhận ActivityLog.

    Output (Đầu ra):
        - TaskResponse: Đối tượng công việc đã cập nhật thông tin `reviewer`.
        - Raise TaskServiceError ('not_found', 'forbidden', 'bad_request') nếu không hợp lệ.
    """
    task = (
        db.query(Task)
        .options(
            joinedload(Task.assignee_links).joinedload(TaskAssignee.user),
            joinedload(Task.reviewer),
            joinedload(Task.status),
        )
        .filter(Task.id == task_id, Task.deleted_at.is_(None))
        .first()
    )
    if not task:
        raise TaskServiceError(
            "not_found", "Không tìm thấy công việc hoặc công việc đã bị xóa."
        )

    project = check_task_manage_permission(db, task.project_id, current_user.id)
    reviewer_user = _resolve_project_member_users(
        db, task.project_id, [payload.reviewerId]
    )[0]
    task.reviewer_id = reviewer_user.id
    task.reviewer = reviewer_user

    task_key = f"{project.key.upper()}-{task.number}"
    db.add(
        ActivityLog(
            project_id=task.project_id,
            actor_id=current_user.id,
            entity_type="task",
            entity_id=task.id,
            action="updated",
            description=f"Đã cập nhật người duyệt cho công việc {task_key}: {reviewer_user.full_name}",
            changes={
                "key": task_key,
                "reviewerId": str(reviewer_user.id),
            },
            ip_address=sanitize_ip(client_ip),
        )
    )

    db.commit()
    db.refresh(task)
    return task_to_response(task, project_key=project.key)


def update_task_properties(
    db: Session,
    *,
    task_id: uuid.UUID,
    current_user: User,
    payload: UpdateTaskPropertiesRequest,
    client_ip: str | None = None,
) -> TaskResponse:
    """
    Cập nhật các thuộc tính chi tiết của công việc trong TaskDrawer.

    Input (Đầu vào):
        - db (Session): Phiên kết nối cơ sở dữ liệu.
        - task_id (UUID): Định danh công việc cần cập nhật thuộc tính.
        - current_user (User): Người dùng đang thực hiện thao tác.
        - payload (UpdateTaskPropertiesRequest): Thông tin thuộc tính (`description`, `priority`, `assigneeIds`, `startDate`, `endDate`, `overdueReason`, `acceptanceResult`).
        - client_ip (str | None): Địa chỉ IP của client để ghi nhận ActivityLog.

    Output (Đầu ra):
        - TaskResponse: Đối tượng công việc sau khi cập nhật thuộc tính và danh sách người thực hiện.
        - Raise TaskServiceError ('not_found', 'forbidden', 'bad_request') nếu không hợp lệ.
    """
    task = (
        db.query(Task)
        .options(
            joinedload(Task.assignee_links).joinedload(TaskAssignee.user),
            joinedload(Task.reviewer),
            joinedload(Task.status),
        )
        .filter(Task.id == task_id, Task.deleted_at.is_(None))
        .first()
    )
    if not task:
        raise TaskServiceError(
            "not_found", "Không tìm thấy công việc hoặc công việc đã bị xóa."
        )

    project = check_task_manage_permission(db, task.project_id, current_user.id)
    assignee_users = _resolve_project_member_users(
        db, task.project_id, payload.assigneeIds
    )

    task.description = payload.description
    task.priority = payload.priority
    task.start_date = payload.startDate
    task.end_date = payload.endDate
    task.overdue_reason = payload.overdueReason.strip() or None
    task.acceptance_result = payload.acceptanceResult.strip() or None

    task.assignee_links.clear()
    db.flush()
    for assignee in assignee_users:
        link = TaskAssignee(
            task_id=task.id,
            project_id=task.project_id,
            user_id=assignee.id,
        )
        link.user = assignee
        task.assignee_links.append(link)

    task_key = f"{project.key.upper()}-{task.number}"
    db.add(
        ActivityLog(
            project_id=task.project_id,
            actor_id=current_user.id,
            entity_type="task",
            entity_id=task.id,
            action="updated",
            description=f"Đã cập nhật thuộc tính công việc {task_key}",
            changes={
                "key": task_key,
                "priority": task.priority,
                "startDate": task.start_date.isoformat(),
                "endDate": task.end_date.isoformat(),
                "assigneeIds": [str(u.id) for u in assignee_users],
                "overdueReason": task.overdue_reason,
                "acceptanceResult": task.acceptance_result,
            },
            ip_address=sanitize_ip(client_ip),
        )
    )

    db.commit()
    db.refresh(task)
    return task_to_response(task, project_key=project.key)
