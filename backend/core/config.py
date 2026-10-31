import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Absolute path to backend/.env — correct regardless of CWD at startup
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = str(_BACKEND_DIR / ".env")


class Settings(BaseSettings):
    """
    Application Settings powered by Pydantic Settings.
    Reads environment variables from system environment and backend/.env.
    The .env path is resolved absolutely from this file's location so it
    is CWD-independent (safe whether uvicorn is started from the repo root
    or from backend/).
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database Configuration
    DATABASE_URL: str = Field(
        default=f"sqlite+aiosqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'conlatus.db').replace('\\', '/')}",
        description="Database connection URL. Defaults to backend/conlatus.db",
    )
    DB_POOL_SIZE: int = Field(default=10, description="PostgreSQL connection pool size")
    DB_MAX_OVERFLOW: int = Field(default=20, description="PostgreSQL max pool overflow")
    DB_POOL_TIMEOUT: int = Field(default=30, description="Pool connection timeout seconds")
    DB_ECHO: bool = Field(default=False, description="SQLAlchemy engine echo mode")

    # App core settings
    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq API key")
    GROQ_MODEL: str = Field(
        default="openai/gpt-oss-120b",
        description="Primary reasoning Groq model for dialogue and question synthesis",
    )
    GROQ_FALLBACK_MODEL: str = Field(
        default="openai/gpt-oss-20b",
        description="Fallback fast Groq model if primary is unavailable or rate limited",
    )

    # Security & JWT Configuration
    JWT_SECRET_KEY: str = Field(
        default="conlatus_super_secret_jwt_key_2026_change_in_production_32bytes",
        description="Secret key for JWT token signing",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, description="Access token expiration in minutes")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token expiration in days")
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"],
        description="Allowed CORS origins",
    )

    # Safe Exam Browser (SEB) Configuration
    SEB_CONFIG_KEY: str = Field(
        default="",
        description="Comma-separated Safe Exam Browser Config Keys for request verification",
    )
    DEV_SKIP_SEB: bool = Field(
        default=False,
        description="If True, bypasses Safe Exam Browser checks in development",
    )

    @property
    def is_sqlite(self) -> bool:
        """Returns True if database dialect is SQLite."""
        return "sqlite" in self.DATABASE_URL.lower()

    @property
    def is_postgres(self) -> bool:
        """Returns True if database dialect is PostgreSQL."""
        url_lower = self.DATABASE_URL.lower()
        return "postgres" in url_lower or "postgresql" in url_lower

    @property
    def async_database_url(self) -> str:
        """
        Normalizes DATABASE_URL for SQLAlchemy 2.0 Async Engine.
        Converts sqlite:// -> sqlite+aiosqlite://
        Converts postgresql:// or postgres:// -> postgresql+asyncpg://
        Converts postgresql:// and not postgresql+asyncpg:// -> postgresql+asyncpg://
        """
        url = self.DATABASE_URL.strip()
        if url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
            return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """
        Normalizes DATABASE_URL for synchronous contexts like Alembic migrations.
        Converts sqlite+aiosqlite:// -> sqlite://
        Converts postgresql+asyncpg:// -> postgresql://
        Converts postgresql:// or postgres:// -> postgresql://
        """
        url = self.DATABASE_URL.strip()
        if url.startswith("sqlite+aiosqlite://"):
            return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def engine_kwargs(self) -> Dict[str, Any]:
        """
        Returns dialect-agnostic engine creation options.
        Configures SQLite for WAL mode & multi-thread access.
        Configures PostgreSQL for connection pooling and pool pre-ping.
        """
        kwargs: Dict[str, Any] = {"echo": self.DB_ECHO}

        if self.is_sqlite:
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs.update(
                {
                    "pool_size": self.DB_POOL_SIZE,
                    "max_overflow": self.DB_MAX_OVERFLOW,
                    "pool_timeout": self.DB_POOL_TIMEOUT,
                    "pool_pre_ping": True,
                }
            )

        return kwargs


settings = Settings()
