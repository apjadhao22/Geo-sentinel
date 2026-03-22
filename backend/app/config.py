from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://redis:6379/0"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "satellite-imagery"
    minio_secure: bool = False

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 480

    imagery_provider: str = "sentinel2"
    sentinel2_client_id: str = ""
    sentinel2_client_secret: str = ""

    pcmc_center_lat: float = 18.6298
    pcmc_center_lng: float = 73.7997

    min_detection_area_sqm: float = 50.0

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
