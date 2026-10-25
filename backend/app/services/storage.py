"""Lưu/đọc file trên MinIO (S3 API). Database chỉ giữ metadata + object_key."""
from collections.abc import Iterator
from typing import BinaryIO

from minio import Minio

from app.core.config import settings


class StorageError(Exception):
    """Không thao tác được với MinIO (mất kết nối, sai khóa, bucket lỗi...)."""


_client: Minio | None = None
_bucket_ready = False


def _get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=settings.MINIO_SECURE,
        )
    return _client


def ensure_bucket() -> None:
    """Tự tạo bucket nếu chưa có -> không cần tạo tay trên MinIO Console."""
    global _bucket_ready
    if _bucket_ready:
        return
    try:
        client = _get_client()
        if not client.bucket_exists(settings.MINIO_BUCKET):
            client.make_bucket(settings.MINIO_BUCKET)
        _bucket_ready = True
    except Exception as exc:  # noqa: BLE001
        raise StorageError(str(exc)) from exc


def put_object(object_key: str, data: BinaryIO, size: int, content_type: str) -> None:
    ensure_bucket()
    try:
        _get_client().put_object(
            settings.MINIO_BUCKET, object_key, data, length=size, content_type=content_type
        )
    except Exception as exc:  # noqa: BLE001
        raise StorageError(str(exc)) from exc


def remove_object(object_key: str) -> None:
    try:
        _get_client().remove_object(settings.MINIO_BUCKET, object_key)
    except Exception:  # noqa: BLE001 - dọn dẹp, không làm hỏng luồng chính
        pass


def open_stream(object_key: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
    """Mở object và trả generator; đảm bảo đóng kết nối khi xong."""
    ensure_bucket()
    try:
        response = _get_client().get_object(settings.MINIO_BUCKET, object_key)
    except Exception as exc:  # noqa: BLE001
        raise StorageError(str(exc)) from exc

    def iterator() -> Iterator[bytes]:
        try:
            yield from response.stream(chunk_size)
        finally:
            response.close()
            response.release_conn()

    return iterator()
