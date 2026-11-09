"""Application configuration management using Pydantic Settings.

Follows 12-factor cloud configuration rules; values are sourced from environment
variables with sensible local development defaults.
"""

from typing import List, Optional

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production configuration schema for CloudOps Sentinel."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # 1. Application Runtime
    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    APP_NAME: str = Field(default="CloudOps Sentinel", description="System identifier")
    APP_VERSION: str = Field(default="0.1.0", description="Semantic version")
    DEBUG: bool = Field(default=False, description="Debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Logging threshold")
    API_V1_PREFIX: str = Field(default="/api/v1", description="API route prefix")
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed web dashboard origins",
    )
    SECRET_KEY: str = Field(
        default="cloudops-sentinel-dev-secret-key-change-in-production-32bytes",
        description="JWT/Session secret",
    )

    # 2. Sentinel Metadata Database
    POSTGRES_SERVER: str = Field(default="localhost", description="PostgreSQL host")
    POSTGRES_PORT: int = Field(default=5434, description="PostgreSQL port")
    POSTGRES_DB: str = Field(default="sentinel_db", description="Database name")
    POSTGRES_USER: str = Field(default="sentinel_admin", description="Database user")
    POSTGRES_PASSWORD: str = Field(
        default="sentinel_secret_dev_pass", description="Database password"
    )

    # Optional explicit overrides
    DATABASE_URL: Optional[str] = None
    SYNC_DATABASE_URL: Optional[str] = None

    # Connection Pool Settings
    DB_POOL_SIZE: int = Field(default=10, description="Active connection pool limit")
    DB_MAX_OVERFLOW: int = Field(default=20, description="Max overflow connections")
    DB_POOL_TIMEOUT: int = Field(
        default=30, description="Connection acquisition timeout"
    )
    DB_POOL_RECYCLE: int = Field(
        default=1800, description="Stale socket recycle period in sec"
    )

    # 3. Monitored Target Database Defaults
    TARGET_POSTGRES_SERVER: str = "localhost"
    TARGET_POSTGRES_PORT: int = 5433
    TARGET_POSTGRES_DB: str = "ecommerce_production"
    TARGET_POSTGRES_USER: str = "monitor_agent"
    TARGET_POSTGRES_PASSWORD: str = "CHANGE_ME_TARGET_SECURE_PASSWORD"
    TARGET_DATABASE_URL: Optional[str] = None

    # 4. Telemetry & Alerting Thresholds
    PROMETHEUS_METRICS_ENABLED: bool = True
    METRICS_SCRAPE_INTERVAL_SECONDS: int = 15
    SLOW_QUERY_THRESHOLD_MS: int = 500
    CONNECTION_POOL_WARNING_THRESHOLD: float = 0.80
    CONNECTION_POOL_CRITICAL_THRESHOLD: float = 0.95
    CACHE_HIT_RATIO_MIN_THRESHOLD: float = 0.90

    # 5. AWS Cloud Integration
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BACKUP_BUCKET: str = "cloudops-sentinel-backups-dev"
    S3_BACKUP_PREFIX: str = "db-snapshots/"
    S3_STORAGE_CLASS: str = "STANDARD_IA"
    CLOUDWATCH_METRICS_ENABLED: bool = False
    CLOUDWATCH_NAMESPACE: str = "CloudOpsSentinel/Databases"

    # 6. Incident Management Integrations
    ALERT_WEBHOOK_URL: Optional[str] = None
    PAGERDUTY_ROUTING_KEY: Optional[str] = None

    # 7. Operational Automation
    BACKUP_RETENTION_DAYS: int = 7
    BACKUP_COMPRESSION_LEVEL: int = 6
    AUTO_VACUUM_ANALYZE_ENABLED: bool = True

    @model_validator(mode="after")
    def validate_production_credentials(self) -> "Settings":
        """Guards against using unrotated development passwords in production."""
        if self.ENVIRONMENT.lower() == "production":
            if self.POSTGRES_PASSWORD == "sentinel_secret_dev_pass":
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: Default POSTGRES_PASSWORD cannot be used in production environment."
                )
            if "change-in-production" in self.SECRET_KEY.lower():
                raise ValueError(
                    "CRITICAL SECURITY VIOLATION: Default SECRET_KEY cannot be used in production environment."
                )
        return self

    @computed_field  # type: ignore[misc]
    @property
    def async_database_url(self) -> str:
        """Returns the asyncpg connection string for FastAPI async operations."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def sync_database_url(self) -> str:
        """Returns standard psycopg2 connection string for Alembic migrations."""
        if self.SYNC_DATABASE_URL:
            return self.SYNC_DATABASE_URL
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
