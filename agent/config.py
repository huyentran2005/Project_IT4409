import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """Tập trung cấu hình chatbot lấy từ .env chung của dự án."""

    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_key: str | None = os.getenv("QDRANT_API_KEY") or None
    collection: str = os.getenv("QDRANT_COLLECTION", "documents_native_bm25")
    documents_dir: Path = (PROJECT_DIR / os.getenv("DOCS_DIR", "docs")).resolve()
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1200"))
    overlap: int = int(os.getenv("CHUNK_OVERLAP", "180"))
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    embedding_model: str = os.getenv(
        "OPENROUTER_EMBEDDING_MODEL", "nvidia/nemotron-3.5-embed-8b:free"
    )
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini").lower()


settings = Settings()

