from pathlib import Path
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agent.qa import answer_question
from agent.schemas import AskRequest, IngestRequest
from agent.service import ingest_path, safe_target
from agent.store import project_collection_name, store
from app.api.project_content import ProjectAccess, project_permission
from app.db.session import get_db
from app.models.project_chat import ProjectChatMessage, ProjectChatSession
from app.schemas.project_chat import ProjectChatAskRequest

router = APIRouter(prefix="/chatbot", tags=["document chatbot"])
project_router = APIRouter(prefix="/projects/{project_id}/chatbot", tags=["project document chatbot"])


@router.get("/health")
def health() -> dict:
    """Báo trạng thái kết nối từ backend tới Qdrant."""
    return {"ok": True, "qdrant": store.is_ready()}


@router.post("/ingest")
def ingest(request: IngestRequest) -> dict:
    """Nạp một file hoặc toàn bộ PDF/DOC/DOCX trong thư mục tài liệu."""
    try:
        return ingest_path(safe_target(request.path))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ask")
async def ask(request: AskRequest) -> dict:
    """Hybrid search tài liệu và sinh câu trả lời có dẫn nguồn."""
    try:
        result = await answer_question(request.question, request.top_k)
        sources = [
            {
                "file": Path(item["source"]).name,
                "page": item.get("page"),
                "headings": item.get("headings"),
                "score": item["score"],
            }
            for item in result.pop("contexts", [])
        ]
        return {**result, "sources": sources}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@project_router.post("/ask")
async def ask_project_documents(
    request: ProjectChatAskRequest,
    access: ProjectAccess = Depends(project_permission("project.view")),
    db: Session = Depends(get_db),
) -> dict:
    """Hỏi tài liệu dự án và lưu hội thoại riêng theo user/project."""
    session = None
    if request.session_id:
        session = (
            db.query(ProjectChatSession)
            .filter(
                ProjectChatSession.id == request.session_id,
                ProjectChatSession.project_id == access.project_id,
                ProjectChatSession.user_id == access.user.id,
            )
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện")

    history = []
    if session:
        recent_messages = (
            db.query(ProjectChatMessage)
            .filter(ProjectChatMessage.session_id == session.id)
            .order_by(ProjectChatMessage.created_at.desc())
            .limit(8)
            .all()
        )
        history = [
            {"role": item.role, "content": item.content}
            for item in reversed(recent_messages)
        ]

    try:
        result = await answer_question(
            request.question,
            request.top_k,
            collection_name=project_collection_name(str(access.project_id)),
            history=history,
        )
        sources = [
            {
                "file": item.get("source_name") or Path(item["source"]).name,
                "page": item.get("page"),
                "headings": item.get("headings"),
                "score": item["score"],
            }
            for item in result.pop("contexts", [])
        ]
        if not sources:
            result["answer"] = "Dự án chưa có tài liệu phù hợp đã được xử lý. Hãy tải tài liệu PDF hoặc DOCX lên trước."
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if session is None:
        session = ProjectChatSession(
            project_id=access.project_id,
            user_id=access.user.id,
            title=request.question.strip()[:180],
        )
        db.add(session)
        db.flush()

    session.updated_at = datetime.now(timezone.utc)
    user_message = ProjectChatMessage(
        session_id=session.id,
        role="user",
        content=request.question.strip(),
        sources=[],
    )
    assistant_message = ProjectChatMessage(
        session_id=session.id,
        role="assistant",
        content=result["answer"],
        sources=sources,
    )
    db.add_all([user_message, assistant_message])
    db.commit()
    db.refresh(session)
    db.refresh(user_message)
    db.refresh(assistant_message)
    return {
        **result,
        "sessionId": str(session.id),
        "sources": sources,
        "messages": [
            _chat_message_out(user_message),
            _chat_message_out(assistant_message),
        ],
    }


def _chat_message_out(message: ProjectChatMessage) -> dict:
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "sources": message.sources or [],
        "createdAt": message.created_at.isoformat(),
    }


@project_router.get("/history")
def list_project_chat_history(
    access: ProjectAccess = Depends(project_permission("project.view")),
    db: Session = Depends(get_db),
) -> list[dict]:
    sessions = (
        db.query(ProjectChatSession)
        .filter(
            ProjectChatSession.project_id == access.project_id,
            ProjectChatSession.user_id == access.user.id,
        )
        .order_by(ProjectChatSession.updated_at.desc())
        .all()
    )
    return [
        {
            "id": str(session.id),
            "title": session.title,
            "createdAt": session.created_at.isoformat(),
            "updatedAt": session.updated_at.isoformat(),
        }
        for session in sessions
    ]


@project_router.get("/history/{session_id}")
def get_project_chat_history(
    session_id: uuid.UUID,
    access: ProjectAccess = Depends(project_permission("project.view")),
    db: Session = Depends(get_db),
) -> dict:
    session = (
        db.query(ProjectChatSession)
        .filter(
            ProjectChatSession.id == session_id,
            ProjectChatSession.project_id == access.project_id,
            ProjectChatSession.user_id == access.user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện")
    messages = (
        db.query(ProjectChatMessage)
        .filter(ProjectChatMessage.session_id == session.id)
        .order_by(ProjectChatMessage.created_at.asc())
        .all()
    )
    return {
        "id": str(session.id),
        "title": session.title,
        "messages": [_chat_message_out(message) for message in messages],
    }


@project_router.delete("/history")
def reset_project_chat_history(
    access: ProjectAccess = Depends(project_permission("project.view")),
    db: Session = Depends(get_db),
) -> dict:
    """Xóa mọi phiên và tin nhắn của user hiện tại trong project hiện tại."""
    deleted = (
        db.query(ProjectChatSession)
        .filter(
            ProjectChatSession.project_id == access.project_id,
            ProjectChatSession.user_id == access.user.id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"deletedSessions": deleted}
