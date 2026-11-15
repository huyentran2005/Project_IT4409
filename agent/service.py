from pathlib import Path

from .config import settings
from .store import store

SUPPORTED_EXTENSIONS = {".pdf", ".doc", ".docx"}


def safe_target(raw_path: str | None) -> Path:
    """Chỉ cho phép ingest file hoặc thư mục nằm trong DOCS_DIR."""
    target = (settings.documents_dir / raw_path).resolve() if raw_path else settings.documents_dir
    if target != settings.documents_dir and settings.documents_dir not in target.parents:
        raise ValueError("Path phải nằm trong DOCS_DIR")
    if not target.exists():
        raise FileNotFoundError(str(target))
    return target


def ingest_path(target: Path) -> dict:
    """Nạp một file hoặc quét đệ quy mọi tài liệu được hỗ trợ."""
    paths = [target] if target.is_file() else [
        path for path in target.rglob("*") if path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    details = {str(path.relative_to(settings.documents_dir)): store.ingest(path) for path in paths}
    return {"files": len(details), "chunks": sum(details.values()), "details": details}

