"""Dispatch background document processing jobs."""

import uuid

from sqlalchemy.orm import Session

from app.models.project_content import ProjectDocument
from app.tasks.document_processing import process_project_document


def enqueue_document_processing(doc: ProjectDocument, db: Session) -> None:
    task_id = str(uuid.uuid4())
    doc.processing_status = "queued"
    doc.processing_error = None
    doc.processing_task_id = task_id
    db.commit()

    try:
        process_project_document.apply_async(args=[str(doc.id)], task_id=task_id)
    except Exception as exc:
        doc.processing_status = "failed"
        doc.processing_error = f"Không đưa được job vào hàng đợi: {exc}"[:2000]
        db.commit()
