"""Download uploaded documents from MinIO, process them and index their content."""

import json
import shutil
import tempfile
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from agent.chunking import make_chunks
from agent.loaders import read_document
from agent.store import project_collection_name, store
from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.project_content import ProjectDocument
from app.services import storage


@celery_app.task(bind=True, name="documents.process_project_document", max_retries=3)
def process_project_document(self, document_id: str) -> dict:
    db: Session = SessionLocal()
    temp_path: Path | None = None
    try:
        doc = db.get(ProjectDocument, uuid.UUID(document_id))
        if not doc or doc.deleted_at is not None:
            return {"status": "ignored", "document_id": document_id}

        doc.processing_status = "processing"
        doc.processing_error = None
        db.commit()
        object_key = doc.object_key
        suffix = Path(doc.name).suffix.lower()
        project_id = str(doc.project_id)
        source = f"project-document:{doc.id}"
        document_name = doc.name
        stored_processed_key = doc.processed_object_key

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            for chunk in storage.open_stream(object_key):
                temp_file.write(chunk)

        if suffix == ".doc" and not (shutil.which("soffice") or shutil.which("libreoffice")):
            doc.processing_status = "unsupported"
            doc.processing_error = "Worker chưa cài LibreOffice để đọc file .doc; hãy tải lên .docx hoặc PDF."
            db.commit()
            return {"status": doc.processing_status, "document_id": document_id}

        chunks = make_chunks(read_document(temp_path))
        if not chunks:
            raise ValueError("Không trích xuất được nội dung văn bản từ tài liệu.")

        store.ingest(
            temp_path,
            source=source,
            source_name=document_name,
            project_id=project_id,
            collection_name=project_collection_name(project_id),
        )

        processed_key = stored_processed_key or f"{object_key}.processed.json"
        processed_data = json.dumps(
            {"document_id": document_id, "name": document_name, "chunks": chunks},
            ensure_ascii=False,
        ).encode("utf-8")
        from io import BytesIO

        storage.put_object(
            processed_key,
            BytesIO(processed_data),
            len(processed_data),
            "application/json; charset=utf-8",
        )

        doc = db.get(ProjectDocument, uuid.UUID(document_id))
        if doc:
            doc.processed_object_key = processed_key
            doc.processing_status = "completed"
            doc.processing_error = None
            db.commit()
        return {"status": "completed", "document_id": document_id, "chunks": len(chunks)}
    except Exception as exc:
        db.rollback()
        doc = db.get(ProjectDocument, uuid.UUID(document_id))
        if doc:
            final_attempt = self.request.retries >= self.max_retries
            doc.processing_status = "failed" if final_attempt else "queued"
            doc.processing_error = str(exc)[:2000]
            db.commit()
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=min(60, 2 ** (self.request.retries + 1)))
        raise
    finally:
        db.close()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
