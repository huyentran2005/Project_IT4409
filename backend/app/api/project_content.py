"""Meeting và tài liệu dự án (file lưu trên MinIO).

Quyền (theo project_members -> project_role_permissions -> permissions):
  - xem danh sách / tải file : project.view
  - tạo meeting              : task.manage   (chưa có mã quyền riêng cho meeting)
  - tải lên / xóa tài liệu   : document.manage
"""
import json
import mimetypes
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.project_content import Meeting, MeetingAttendee, ProjectDocument
from app.models.user import User
from app.schemas.project_content import DocumentOut, MeetingCreate, MeetingOut
from app.services import storage

router = APIRouter(prefix="/projects/{project_id}", tags=["meetings & documents"])

# Chỉ cho phép định dạng văn phòng/ảnh phổ biến. KHÔNG cho html/svg/js để tránh XSS khi tải về.
ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "txt", "md", "csv", "png", "jpg", "jpeg", "gif", "webp", "zip",
}


@dataclass
class ProjectAccess:
    project_id: uuid.UUID
    user: User
    timezone: str


def project_permission(code: str):
    """Dependency: user phải là thành viên dự án và vai trò có quyền `code`."""

    def dependency(
        project_id: uuid.UUID,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> ProjectAccess:
        member = db.execute(
            text(
                "SELECT p.timezone FROM project_members pm "
                "JOIN projects p ON p.id = pm.project_id AND p.deleted_at IS NULL "
                "WHERE pm.project_id = :pid AND pm.user_id = :uid"
            ),
            {"pid": project_id, "uid": user.id},
        ).first()
        if not member:
            # Không tiết lộ dự án có tồn tại hay không
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy dự án")

        allowed = db.execute(
            text(
                "SELECT 1 FROM project_members pm "
                "JOIN project_role_permissions rp ON rp.role_id = pm.role_id "
                "JOIN permissions pe ON pe.id = rp.permission_id "
                "WHERE pm.project_id = :pid AND pm.user_id = :uid AND pe.code = :code"
            ),
            {"pid": project_id, "uid": user.id, "code": code},
        ).first()
        if not allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không có quyền thực hiện thao tác này")
        return ProjectAccess(project_id=project_id, user=user, timezone=member[0])

    return dependency


def _log_activity(db: Session, access: ProjectAccess, entity_type: str, entity_id: uuid.UUID,
                  action: str, description: str) -> None:
    db.execute(
        text(
            "INSERT INTO activity_logs (project_id, actor_id, entity_type, entity_id, action, description, changes) "
            "VALUES (:pid, :uid, :et, :eid, :act, :desc, CAST(:chg AS jsonb))"
        ),
        {"pid": access.project_id, "uid": access.user.id, "et": entity_type, "eid": entity_id,
         "act": action, "desc": description, "chg": json.dumps({})},
    )


# --------------------------------------------------------------------------- Meetings
def _meeting_out(m: Meeting, tz: str) -> MeetingOut:
    zone = ZoneInfo(tz)
    start, end = m.starts_at.astimezone(zone), m.ends_at.astimezone(zone)
    return MeetingOut(
        id=str(m.id), projectId=str(m.project_id), title=m.title,
        date=start.date().isoformat(), startTime=start.strftime("%H:%M"), endTime=end.strftime("%H:%M"),
        location=m.location, meetingUrl=m.meeting_url, description=m.description or "",
    )


@router.post("/meetings", response_model=MeetingOut, status_code=status.HTTP_201_CREATED)
def create_meeting(
    body: MeetingCreate,
    access: ProjectAccess = Depends(project_permission("task.manage")),
    db: Session = Depends(get_db),
):
    """
    Tạo meeting cho dự án.

    Input: JSON {title, date (YYYY-MM-DD), startTime (HH:MM), endTime (HH:MM), location, meetingUrl, description?}.
    Giờ được hiểu theo múi giờ của dự án (projects.timezone).
    Hiệu ứng: ghi `meetings`, thêm toàn bộ thành viên hiện tại vào `meeting_attendees`, ghi `activity_logs`.
    Output: 201 MeetingOut; 403 không có quyền; 404 không phải thành viên; 422 dữ liệu sai.
    """
    zone = ZoneInfo(access.timezone)
    meeting = Meeting(
        project_id=access.project_id,
        created_by=access.user.id,
        title=body.title,
        description=body.description,
        location=body.location,
        starts_at=datetime.combine(body.date, body.startTime, tzinfo=zone),
        ends_at=datetime.combine(body.date, body.endTime, tzinfo=zone),
        meeting_url=body.meetingUrl,
    )
    db.add(meeting)
    db.flush()

    member_ids = db.execute(
        text("SELECT user_id FROM project_members WHERE project_id = :pid"),
        {"pid": access.project_id},
    ).scalars().all()
    db.add_all(MeetingAttendee(meeting_id=meeting.id, user_id=uid) for uid in member_ids)

    _log_activity(db, access, "meeting", meeting.id, "meeting_created", f"đã tạo meeting · {meeting.title}")
    db.commit()
    db.refresh(meeting)
    return _meeting_out(meeting, access.timezone)


@router.get("/meetings", response_model=list[MeetingOut])
def list_meetings(
    access: ProjectAccess = Depends(project_permission("project.view")),
    db: Session = Depends(get_db),
):
    """Danh sách meeting chưa hủy của dự án, theo thời gian bắt đầu."""
    rows = (
        db.query(Meeting)
        .filter(Meeting.project_id == access.project_id, Meeting.cancelled_at.is_(None))
        .order_by(Meeting.starts_at)
        .all()
    )
    return [_meeting_out(m, access.timezone) for m in rows]


# --------------------------------------------------------------------------- Documents
def _format_size(n: int) -> str:
    if n < 1024 * 1024:
        return f"{max(n / 1024, 0.01):.2f} KB"
    return f"{n / 1024 / 1024:.2f} MB"


def _document_out(doc: ProjectDocument, updated_by_name: str) -> DocumentOut:
    ext = os.path.splitext(doc.name)[1].lstrip(".").upper() or "FILE"
    return DocumentOut(
        id=str(doc.id), name=doc.name, type=ext, size=_format_size(doc.size_bytes),
        updatedAt=doc.updated_at.isoformat(), updatedBy=updated_by_name,
    )


def _clean_filename(raw: str | None) -> str:
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:255]


def _storage_unavailable() -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Không kết nối được kho lưu trữ tệp (MinIO)")


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    access: ProjectAccess = Depends(project_permission("project.view")),
    db: Session = Depends(get_db),
):
    """Danh sách tài liệu chưa xóa, mới cập nhật nhất lên đầu."""
    rows = (
        db.query(ProjectDocument, User.full_name)
        .join(User, User.id == ProjectDocument.updated_by)
        .filter(ProjectDocument.project_id == access.project_id, ProjectDocument.deleted_at.is_(None))
        .order_by(ProjectDocument.updated_at.desc())
        .all()
    )
    return [_document_out(doc, name) for doc, name in rows]


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    access: ProjectAccess = Depends(project_permission("document.manage")),
    db: Session = Depends(get_db),
):
    """
    Tải tài liệu lên MinIO và lưu metadata vào `project_documents`.

    Input: multipart/form-data, trường `file`. Tối đa MAX_UPLOAD_MB (mặc định 25 MB);
           chỉ nhận: pdf, doc(x), xls(x), ppt(x), txt, md, csv, png, jpg, gif, webp, zip.
    Output: 201 DocumentOut; 400 file rỗng/thiếu tên; 413 quá lớn; 415 sai định dạng; 503 MinIO lỗi.
    """
    name = _clean_filename(file.filename)
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Thiếu tên tệp")
    ext = os.path.splitext(name)[1].lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Định dạng không được hỗ trợ. Cho phép: " + ", ".join(sorted(ALLOWED_EXTENSIONS)),
        )

    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tệp rỗng")
    if size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Tệp vượt quá {settings.MAX_UPLOAD_MB} MB"
        )

    # Không tin Content-Type do client gửi: suy ra từ đuôi file
    mime = mimetypes.guess_type(f"x.{ext}")[0] or "application/octet-stream"
    # Khóa object do server sinh, không chứa tên người dùng -> không có path traversal / ký tự lạ
    object_key = f"projects/{access.project_id}/documents/{uuid.uuid4()}.{ext}"

    try:
        storage.put_object(object_key, file.file, size, mime)
    except storage.StorageError:
        raise _storage_unavailable()

    doc = ProjectDocument(
        project_id=access.project_id, uploaded_by=access.user.id, updated_by=access.user.id,
        name=name, object_key=object_key, mime_type=mime, size_bytes=size,
    )
    try:
        db.add(doc)
        db.flush()
        _log_activity(db, access, "document", doc.id, "created", f"đã tải lên tài liệu · {name}")
        db.commit()
    except Exception:
        db.rollback()
        storage.remove_object(object_key)  # tránh file mồ côi trên MinIO
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Không lưu được thông tin tài liệu")
    db.refresh(doc)
    return _document_out(doc, access.user.full_name)


def _get_document(db: Session, access: ProjectAccess, document_id: uuid.UUID) -> ProjectDocument:
    doc = (
        db.query(ProjectDocument)
        .filter(
            ProjectDocument.id == document_id,
            ProjectDocument.project_id == access.project_id,  # chặn đọc tài liệu của dự án khác
            ProjectDocument.deleted_at.is_(None),
        )
        .first()
    )
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy tài liệu")
    return doc


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: uuid.UUID,
    access: ProjectAccess = Depends(project_permission("project.view")),
    db: Session = Depends(get_db),
):
    """Tải tài liệu. Backend đọc từ MinIO và stream về (MinIO không mở trực tiếp ra trình duyệt)."""
    doc = _get_document(db, access, document_id)
    try:
        stream = storage.open_stream(doc.object_key)
    except storage.StorageError:
        raise _storage_unavailable()
    return StreamingResponse(
        stream,
        media_type=doc.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.name)}",
            "Content-Length": str(doc.size_bytes),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    access: ProjectAccess = Depends(project_permission("document.manage")),
    db: Session = Depends(get_db),
):
    """Xóa mềm (đặt deleted_at). File trên MinIO được giữ lại để có thể khôi phục."""
    doc = _get_document(db, access, document_id)
    doc.deleted_at = datetime.now(ZoneInfo("UTC"))
    doc.updated_by = access.user.id
    _log_activity(db, access, "document", doc.id, "deleted", f"đã xóa tài liệu · {doc.name}")
    db.commit()
