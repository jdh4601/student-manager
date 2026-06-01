from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


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
    # Outbox CDC — Postgres LISTEN/NOTIFY channels (ADR-003)
    listen_notify_catchup_interval: float = 60.0
    listen_notify_idle_poll_interval: float = 0.5
    outbox_max_retries: int = 3

    # Chat / LLM (OpenAI API; spec §10)
    openai_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 10.0
    llm_max_tokens: int = 1024
    # "auto" picks OpenAI when key present, else stub. Set to "stub" to force stub.
    llm_provider: str = "auto"

    # 배포 환경 구분 — "production"에서는 OAuth stub(인증 우회) 금지.
    environment: str = "dev"

    # Teacher Google OAuth (REQ-001). "auto" → real when google_client_id set, else stub.
    oauth_provider: str = "auto"
    # stub OAuth는 인증 우회가 가능하므로 production에서는 기본 차단.
    # 데모 목적으로 명시적 허용이 필요할 때만 True (의식적 선택).
    allow_oauth_stub: bool = False
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:5173/auth/oauth/google/callback"
    # edu 도메인 화이트리스트 — 이 도메인 이메일만 교사 권한 부여. CSV로 주입.
    # NoDecode: pydantic-settings의 기본 JSON 디코딩을 끄고 split_domains(CSV)가 처리하게 함.
    # (없으면 "inu.ac.kr" 같은 CSV가 JSON 파싱 실패로 SettingsError를 일으킴)
    allowed_teacher_domains: Annotated[list[str], NoDecode] = []
    # 신규 OAuth 교사가 배정될 학교 (데모용). 운영에선 School.domain 매핑으로 대체.
    oauth_default_school_id: str | None = None

    @field_validator("allowed_teacher_domains", mode="before")
    @classmethod
    def split_domains(cls, v: object) -> object:
        # 환경변수에서 "a.edu,b.ac.kr" CSV로 들어오면 리스트로 변환.
        if isinstance(v, str):
            return [d.strip().lower() for d in v.split(",") if d.strip()]
        return v

    # extra="ignore": .env는 docker-entrypoint와 공유되어 Settings 필드가 아닌 키
    # (RUN_SEED 등)를 포함할 수 있다. forbid면 그런 키가 부팅을 깨뜨린다.
    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
