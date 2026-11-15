import logging
import time
import uuid
from pathlib import Path

import httpx
from qdrant_client import QdrantClient, models

from .chunking import make_chunks
from .config import settings
from .loaders import read_document

logger = logging.getLogger(__name__)


class EmbeddingServiceError(RuntimeError):
    """OpenRouter không khả dụng để tạo embedding sau khi đã thử lại."""


def project_collection_name(project_id: str) -> str:
    """Tách vector collection theo project để tránh trộn tài liệu giữa các dự án."""
    return f"{settings.collection}_{project_id.replace('-', '')}"


class VectorStore:
    """Quản lý embedding, lưu trữ và hybrid search trên Qdrant."""

    def __init__(self) -> None:
        """Khởi tạo Qdrant client; embedding dense được gọi qua OpenRouter."""
        self.client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_key)

    def _dense(self, texts: list[str], input_type: str) -> list[list[float]]:
        """Gọi OpenRouter Nemotron để sinh dense embedding theo batch."""
        if not settings.openrouter_api_key:
            raise RuntimeError("Thiếu OPENROUTER_API_KEY")
        for attempt in range(2):
            try:
                response = httpx.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                    json={"model": settings.embedding_model, "input": texts, "input_type": input_type},
                    timeout=45,
                )
                response.raise_for_status()
                return [
                    item["embedding"]
                    for item in sorted(response.json()["data"], key=lambda item: item["index"])
                ]
            except httpx.HTTPStatusError as exc:
                retryable = exc.response.status_code in {429, 502, 503, 504}
                if not retryable or attempt == 1:
                    raise EmbeddingServiceError(
                        f"OpenRouter embeddings lỗi HTTP {exc.response.status_code}"
                    ) from exc
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt == 1:
                    raise EmbeddingServiceError(
                        "OpenRouter embeddings không phản hồi sau 2 lần thử"
                    ) from exc
            time.sleep(1)
        raise EmbeddingServiceError("Không thể tạo embedding từ OpenRouter")

    def _ensure_collection(self, vector_size: int, collection_name: str) -> None:
        """Tạo dense collection và full-text index có BM25 scoring."""
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
                },
            )
        if "text" not in self.client.get_collection(collection_name).payload_schema:
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="text",
                field_schema=models.TextIndexParams(type=models.TextIndexType.TEXT, scoring=True),
                wait=True,
            )

    def _rerank(self, question: str, points: list, top_k: int) -> list[dict]:
        """Xếp lại các ứng viên Qdrant bằng OpenRouter Rerank API."""
        if not points:
            return []
        response = httpx.post(
            "https://openrouter.ai/api/v1/rerank",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json={
                "model": settings.rerank_model,
                "query": question,
                "documents": [(point.payload or {}).get("text", "") for point in points],
                "top_n": min(top_k, len(points)),
            },
            timeout=45,
        )
        response.raise_for_status()
        ranked = []
        for item in response.json().get("results", []):
            index = item.get("index")
            if isinstance(index, int) and 0 <= index < len(points):
                ranked.append(
                    {
                        **(points[index].payload or {}),
                        "score": item.get("relevance_score", points[index].score),
                    }
                )
        return ranked

    def is_ready(self) -> bool:
        """Kiểm tra Qdrant có phản hồi hay không."""
        return self.client.get_collections() is not None

    def ingest(
        self,
        path: Path,
        *,
        source: str | None = None,
        source_name: str | None = None,
        project_id: str | None = None,
        collection_name: str | None = None,
    ) -> int:
        """Chunk, embed và thay thế dữ liệu cũ của một tài liệu."""
        collection = collection_name or settings.collection
        chunks = make_chunks(read_document(path))
        if not chunks:
            return 0
        texts = [item["text"] for item in chunks]
        dense = self._dense(texts, "search_document")
        self._ensure_collection(len(dense[0]), collection)
        source = source or str(path.resolve())
        self.client.delete(
            collection,
            points_selector=models.FilterSelector(filter=models.Filter(must=[
                models.FieldCondition(key="source", match=models.MatchValue(value=source))
            ])),
            wait=True,
        )
        points = [
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source}:{index}")),
                vector={"dense": dense[index]},
                payload={
                    **chunk,
                    "source": source,
                    "source_name": source_name or path.name,
                    "chunk": index,
                    **({"project_id": project_id} if project_id else {}),
                },
            )
            for index, chunk in enumerate(chunks)
        ]
        for start in range(0, len(points), 64):
            self.client.upsert(collection, points=points[start:start + 64], wait=True)
        return len(points)

    def delete_source(self, source: str, collection_name: str) -> None:
        if not self.client.collection_exists(collection_name):
            return
        self.client.delete(
            collection_name,
            points_selector=models.FilterSelector(filter=models.Filter(must=[
                models.FieldCondition(key="source", match=models.MatchValue(value=source))
            ])),
            wait=True,
        )

    def search(
        self, question: str, top_k: int, collection_name: str | None = None,
        source_filter: list[str] | None = None,
    ) -> list[dict]:
        """Tìm dense và native BM25 rồi hợp nhất thứ hạng bằng RRF."""
        collection = collection_name or settings.collection
        if not self.client.collection_exists(collection):
            return []
        dense_query = self._dense([question], "search_query")[0]
        candidate_k = max(top_k * 3, top_k)
        result = self.client.query_points(
            collection_name=collection,
            prefetch=[
                models.Prefetch(query=dense_query, using="dense", limit=top_k * 3),
                models.Prefetch(
                    query=models.TextQuery(text=question), using="text", limit=top_k * 3
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=(models.Filter(must=[models.FieldCondition(
                key="source", match=models.MatchAny(any=source_filter)
            )]) if source_filter else None),
            limit=candidate_k,
            with_payload=True,
        )
        try:
            return self._rerank(question, result.points, top_k)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning("OpenRouter rerank thất bại; dùng thứ tự hybrid search: %s", exc)
            return [{**(point.payload or {}), "score": point.score} for point in result.points[:top_k]]


store = VectorStore()
