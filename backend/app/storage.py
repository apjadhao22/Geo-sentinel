from datetime import timedelta

from minio import Minio

from app.config import settings

minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure,
)


def ensure_bucket():
    if not minio_client.bucket_exists(settings.minio_bucket):
        minio_client.make_bucket(settings.minio_bucket)


def upload_image(object_name: str, file_path: str, content_type: str = "image/tiff"):
    ensure_bucket()
    minio_client.fput_object(settings.minio_bucket, object_name, file_path, content_type=content_type)


def get_presigned_url(object_name: str, expires_hours: int = 1) -> str:
    return minio_client.presigned_get_object(
        settings.minio_bucket, object_name, expires=timedelta(hours=expires_hours)
    )


def download_image(object_name: str, file_path: str):
    minio_client.fget_object(settings.minio_bucket, object_name, file_path)
