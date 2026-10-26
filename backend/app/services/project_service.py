"""Tạo dự án: dùng SQL thuần (text) để không phụ thuộc/đụng model Project của nhánh phân quyền."""
from sqlalchemy import bindparam, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.project import CreateProjectRequest, ProjectSummary
from app.schemas.user import user_to_summary

ALL_PERMS = ["project.manage", "member.manage", "task.manage", "document.manage", "project.view"]

# code, tên, mô tả, quyền mặc định (có thể chỉnh theo yêu cầu nhóm)
DEFAULT_ROLES = [
    ("owner", "Chủ dự án", "Toàn quyền với dự án", ALL_PERMS),
    ("manager", "Quản lý", "Quản lý thành viên, công việc và tài liệu",
     ["member.manage", "task.manage", "document.manage", "project.view"]),
    ("member", "Thành viên", "Tạo và cập nhật công việc, tài liệu",
     ["task.manage", "document.manage", "project.view"]),
    ("viewer", "Người xem", "Chỉ xem dự án", ["project.view"]),
]

# code, tên cột, category, màu, WIP limit (khớp board mặc định của frontend)
DEFAULT_STATUSES = [
    ("backlog", "Cần làm", "todo", "#64748b", 8),
    ("in-progress", "Đang làm", "in_progress", "#2563eb", 4),
    ("review", "Đang duyệt", "in_progress", "#d97706", 3),
    ("done", "Hoàn thành", "done", "#0f9f8f", None),
]


class ProjectKeyExists(Exception):
    pass


def create_project(db: Session, owner: User, data: CreateProjectRequest) -> ProjectSummary:
    taken = db.execute(
        text("SELECT 1 FROM projects WHERE upper(key) = :k AND deleted_at IS NULL"),
        {"k": data.key},
    ).first()
    if taken:
        raise ProjectKeyExists()

    try:
        project_id = db.execute(
            text(
                "INSERT INTO projects (owner_id, name, key, description, color) "
                "VALUES (:owner, :name, :key, :description, :color) RETURNING id"
            ),
            {"owner": owner.id, "name": data.name, "key": data.key,
             "description": data.description, "color": data.color},
        ).scalar_one()

        owner_role_id = None
        grant = text(
            "INSERT INTO project_role_permissions (role_id, permission_id) "
            "SELECT :rid, id FROM permissions WHERE code IN :codes"
        ).bindparams(bindparam("codes", expanding=True))
        for position, (code, name, desc, perm_codes) in enumerate(DEFAULT_ROLES):
            role_id = db.execute(
                text(
                    "INSERT INTO project_roles (project_id, code, name, description, is_system, position) "
                    "VALUES (:pid, :code, :name, :desc, true, :pos) RETURNING id"
                ),
                {"pid": project_id, "code": code, "name": name, "desc": desc, "pos": position},
            ).scalar_one()
            if code == "owner":
                owner_role_id = role_id
            db.execute(grant, {"rid": role_id, "codes": perm_codes})

        db.execute(
            text("INSERT INTO project_members (project_id, user_id, role_id) VALUES (:pid, :uid, :rid)"),
            {"pid": project_id, "uid": owner.id, "rid": owner_role_id},
        )

        for i, (code, name, category, color, wip) in enumerate(DEFAULT_STATUSES, start=1):
            db.execute(
                text(
                    "INSERT INTO statuses (project_id, code, name, category, color, position, wip_limit) "
                    "VALUES (:pid, :code, :name, :cat, :color, :pos, :wip)"
                ),
                {"pid": project_id, "code": code, "name": name, "cat": category,
                 "color": color, "pos": i * 1000, "wip": wip},
            )
        db.commit()
    except IntegrityError:
        # Hai request cùng key chạy đồng thời: unique index uq_projects_key_active chặn
        db.rollback()
        raise ProjectKeyExists()

    return ProjectSummary(
        id=str(project_id), key=data.key, name=data.name, description=data.description,
        color=data.color, progress=0, members=[user_to_summary(owner)],
    )
