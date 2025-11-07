"""Configuration management for YouTube Feed Aggregator."""

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="YT_", extra="ignore")

    # Security keys
    app_secret_key: str
    token_enc_key: str

    # Google OAuth
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: HttpUrl

    # Database
    database_url: str = "sqlite+aiosqlite:///./dev.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Feed settings
    feed_ttl_seconds: int = 1800  # 30 minutes
    feed_ttl_splay_max: int = 780  # up to 13 minutes randomized
    subs_refresh_minutes: int = 60
    include_shorts: bool = False

    # Pagination
    page_size_default: int = 24
    page_size_max: int = 60

    # CORS
    frontend_origin: str = "http://localhost:5173"

    # Mailgun (for transactional emails)
    mailgun_api_key: str = Field(default="")
    mailgun_domain: str = Field(default="")
    mailgun_from_email: str = Field(default="noreply@example.com")

    # Export Storage Configuration
    export_storage_backend: str = Field(
        default="local", pattern="^(local|gcs)$"
    )  # local or gcs
    export_local_path: str = Field(default="./exports")
    export_url_base: str = Field(
        default="http://localhost:8000"
    )  # Base URL for download links
    export_ttl_hours: int = Field(default=24)  # How long exports are available

    # Google Cloud Storage (only needed if export_storage_backend=gcs)
    gcs_bucket_name: str = Field(default="")
    gcs_credentials_file: str = Field(
        default=""
    )  # Path to service account JSON file

    # Environment
    env: str = Field(default="dev", pattern="^(dev|prod)$")


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get cached settings instance (singleton pattern)."""
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
