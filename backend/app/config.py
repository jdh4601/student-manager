from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/student_manager"

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_async_driver(cls, v: str) -> str:
        # Render (and Heroku) provide plain postgresql:// or postgres:// URLs.
        # SQLAlchemy's asyncio extension requires the +asyncpg driver scheme.
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v
    test_database_url: str = "sqlite+aiosqlite:///./test.db"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    invite_token_expire_hours: int = 72
    password_reset_token_expire_minutes: int = 60
    app_base_url: str = "http://localhost:5173"
    auth_link_delivery: str = "stub"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: float = 10.0
    # Allow both localhost and 127.0.0.1 for Vite dev server to avoid CORS
    # preflight failures (DELETE/PUT) when the dev host differs.
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    # Cookie settings for refresh token
    refresh_cookie_name: str = "refresh_token"
    cookie_secure: bool = False
    cookie_samesite: str = "strict"  # one of: "lax", "strict", "none"
    cookie_path: str = "/"
    # Kafka — outbox-publisher / analytics-worker
    kafka_bootstrap_servers: str = "localhost:9092"

    # Chat / LLM (OpenAI API; spec §10)
    openai_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 10.0
    llm_max_tokens: int = 1024
    # "auto" picks OpenAI when key present, else stub. Set to "stub" to force stub.
    llm_provider: str = "auto"

    model_config = {"env_file": ".env"}


settings = Settings()
