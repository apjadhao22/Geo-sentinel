from datetime import timedelta

from minio import Minio

from app.config import settings

_minio_client: Minio | None = None
_bucket_ensured: bool = False


def get_client() -> Minio:
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _minio_client


def ensure_bucket():
    global _bucket_ensured
    if not _bucket_ensured:
        client = get_client()
        if not client.bucket_exists(settings.minio_bucket):
            client.make_bucket(settings.minio_bucket)
        _bucket_ensured = True


def upload_image(object_name: str, file_path: str, content_type: str = "image/tiff"):
    ensure_bucket()
    get_client().fput_object(settings.minio_bucket, object_name, file_path, content_type=content_type)


def get_presigned_url(object_name: str, expires_hours: int = 1) -> str:
    return get_client().presigned_get_object(
        settings.minio_bucket, object_name, expires=timedelta(hours=expires_hours)
    )


def download_image(object_name: str, file_path: str):
    get_client().fget_object(settings.minio_bucket, object_name, file_path)
