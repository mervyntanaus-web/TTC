from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TTC_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://ttc:ttc@localhost:5432/ttc"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 8

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "ttc-admin"
    s3_secret_key: str = "ttc-admin-secret"
    s3_hot_bucket: str = "ttc-hot"
    s3_cold_bucket: str = "ttc-cold"
    s3_region: str = "us-east-1"

    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"

    # Formats TTC's existing systems produce, per the RFP. mp4/avi/mkv/mpeg-4 are
    # decoded/transcoded for real via ffmpeg. cme/g64x are vendor-proprietary and
    # only get a documented stub decoder until vendor SDKs are available.
    supported_native_formats: tuple[str, ...] = ("mp4", "avi", "mkv", "m4v", "mpeg", "mpg")
    proprietary_formats: tuple[str, ...] = ("cme", "g64", "g64x")

    cold_storage_restore_sla_hours: int = 24

    upload_chunk_size_bytes: int = 8 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
