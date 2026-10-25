import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import func, update
from sqlalchemy.orm import Session, joinedload
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
from app.schemas.task import (
    BoardColumnResponse,
    BoardDataResponse,
    CreateTaskRequest,
    ProjectSummaryResponse,
    TaskResponse,
    task_to_response,
)
from app.schemas.user import user_to_summary
from app.services.auth_service import sanitize_ip


class TaskServiceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


_DEFAULT_PERMISSIONS = [
    ("project.manage", "Quản lý dự án", "Sửa thông tin và cấu hình dự án"),
    ("member.manage", "Quản lý thành viên", "Mời, đổi vai trò và xóa thành viên"),
    ("task.manage", "Quản lý công việc", "Tạo, sửa và di chuyển công việc"),
    ("document.manage", "Quản lý tài liệu", "Tải lên, cập nhật và xóa tài liệu"),
    ("project.view", "Xem dự án", "Xem bảng, thành viên và tài liệu"),
]

_DEFAULT_STATUSES = [
    ("backlog", "Cần làm", "todo", "#64748b", Decimal("1000"), 8),
    ("in-progress", "Đang làm", "in_progress", "#2563eb", Decimal("2000"), 4),
    ("review", "Đang duyệt", "in_progress", "#d97706", Decimal("3000"), 3),
    ("done", "Hoàn thành", "done", "#0f9f8f", Decimal("4000"), None),
]


def ensure_default_project_for_user(db: Session, user: User) -> Project:
    """
    Tìm dự án đầu tiên mà user là thành viên. Nếu user chưa có dự án nào
    (ví dụ: vừa đăng ký hoặc chưa chạy API tạo dự án), tự động khởi tạo
    dự án mặc định đủ Role, Permission và 4 cột Status chuẩn để thao tác ngay trên FE.
    """
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
    if existing:
        return existing

    # Tìm key chưa trùng (TF, TF1, TF2...)
    base_key = "TF"
    candidate_key = base_key
    suffix = 1
    while (
        db.query(Project)
        .filter(
            func.upper(Project.key) == candidate_key,
            Project.deleted_at.is_(None),
        )
        .first()
        is not None
    ):
        candidate_key = f"{base_key}{suffix}"
        suffix += 1

    project = Project(
        owner_id=user.id,
        name="TaskFlow Web App",
        key=candidate_key,
        description="Nền tảng quản lý công việc cho đội ngũ sản phẩm",
        color="#5B5CE2",
        task_sequence=0,
    )
    db.add(project)
    db.flush()

    # Đảm bảo danh mục permissions có đủ 5 mã chuẩn
    perms_by_code: dict[str, Permission] = {}
    for code, name, desc in _DEFAULT_PERMISSIONS:
        perm = db.query(Permission).filter(Permission.code == code).first()
        if not perm:
            perm = Permission(code=code, name=name, description=desc)
            db.add(perm)
            db.flush()
        perms_by_code[code] = perm

    role_configs = [
        (
            "owner",
            "Owner",
            1,
            [
                "project.manage",
                "member.manage",
                "task.manage",
                "document.manage",
                "project.view",
            ],
        ),
        (
            "manager",
            "Manager",
            2,
            ["member.manage", "task.manage", "document.manage", "project.view"],
        ),
        (
            "member",
            "Member",
            3,
            ["task.manage", "document.manage", "project.view"],
        ),
        ("viewer", "Viewer", 4, ["project.view"]),
    ]

    owner_role: ProjectRole | None = None
    for r_code, r_name, r_pos, perm_codes in role_configs:
        role = ProjectRole(
            project_id=project.id,
            code=r_code,
            name=r_name,
            is_system=True,
            position=r_pos,
        )
        db.add(role)
        db.flush()
        if r_code == "owner":
            owner_role = role
        for p_code in perm_codes:
            db.add(
                ProjectRolePermission(
                    role_id=role.id,
                    permission_id=perms_by_code[p_code].id,
                )
            )

    assert owner_role is not None
    db.add(
        ProjectMember(
            project_id=project.id,
            user_id=user.id,
            role_id=owner_role.id,
        )
    )

    for s_code, s_name, s_cat, s_color, s_pos, s_limit in _DEFAULT_STATUSES:
        db.add(
            Status(
                project_id=project.id,
                code=s_code,
                name=s_name,
                category=s_cat,
                color=s_color,
                position=s_pos,
                wip_limit=s_limit,
            )
        )

    db.commit()
    db.refresh(project)
    return project


def resolve_project_id(
    db: Session, project_id_or_alias: str, user: User
) -> uuid.UUID:
    """
    Chuyển chuỗi project_id trên URL thành UUID thực tế.
    Hỗ trợ cả UUID thật lẫn mã giả định 'p-01' trên Frontend khi chưa chọn dự án.
    """
    try:
        return uuid.UUID(project_id_or_alias)
    except (ValueError, TypeError):
        project = ensure_default_project_for_user(db, user)
        return project.id


def check_task_manage_permission(
    db: Session, project_id: uuid.UUID, user_id: uuid.UUID
) -> Project:
    """
    Kiểm tra dự án tồn tại, chưa bị xóa/lưu trữ và người dùng hiện tại
    là thành viên có quyền 'task.manage' trong dự án.
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
            members=[user_to_summary(u) for u in member_users],
        ),
        columns=columns,
    )


def list_project_tasks(
    db: Session,
    *,
    project_id_or_alias: str,
    current_user: User,
) -> list[TaskResponse]:
    """
    Lấy danh sách phẳng toàn bộ các công việc chưa xóa của dự án.
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
    Tạo công việc mới trong dự án:
    1. Kiểm tra dự án & quyền 'task.manage' của người dùng.
    2. Tra cứu trạng thái (status) theo code và kiểm tra WIP limit.
    3. Kiểm tra toàn bộ assigneeIds đều là thành viên của dự án.
    4. Tăng nguyên tử projects.task_sequence để sinh số thứ tự task.
    5. Lưu Task, TaskAssignee và ActivityLog trong cùng 1 transaction.
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
    Xóa mềm công việc (gán tasks.deleted_at = now()):
    1. Tìm công việc chưa bị xóa.
    2. Kiểm tra quyền 'task.manage' của người dùng trên dự án chứa công việc.
    3. Cập nhật deleted_at và ghi nhận ActivityLog.
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
