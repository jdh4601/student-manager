from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppException
from app.dependencies.db import get_db
from app.ratelimit import limiter
from app.routers import auth
from app.routers import semesters
from app.routers import classes
from app.routers import users
from app.routers import feedbacks
from app.routers import grades
from app.routers import counselings
from app.routers import notifications
from app.routers import students
from app.routers import imports
from app.routers import my
from app.routers import analytics
from app.routers import chat



# OpenAPI 태그 메타데이터 — Swagger UI에서 도메인별 그룹 + 설명 노출.
# 팀 개발의 API 합의(contract-first)를 시각적으로 증명하는 단일 진실 공급원.
tags_metadata = [
    {"name": "auth", "description": "로그인·토큰 발급/갱신, 초대 수락, 비밀번호 재설정. access=메모리 / refresh=HttpOnly 쿠키."},
    {"name": "users", "description": "교사·학생·학부모 계정 관리 (role + school_id 범위 검증)."},
    {"name": "students", "description": "학생부 — 기본정보·출결·특기사항 CRUD."},
    {"name": "classes", "description": "학급·담임 매핑 관리."},
    {"name": "semesters", "description": "학기 정의 (1학기 3~8월 / 2학기 9~2월)."},
    {"name": "grades", "description": "성적 입력·수정, 총점·평균·9등급 자동 계산, 레이더 차트 데이터."},
    {"name": "feedbacks", "description": "피드백 작성/공개여부 제어 (학생·학부모 독립 설정)."},
    {"name": "counselings", "description": "상담 기록 — 같은 학교 교사 간 공유 제어."},
    {"name": "notifications", "description": "인앱 알림 — 성적·피드백·상담 업데이트."},
    {"name": "import", "description": "CSV/Excel 일괄 가져오기 (학생·성적)."},
    {"name": "analytics", "description": "분석 대시보드 — analytics 스키마 집계 캐시 read (담임 한정 RBAC)."},
    {"name": "chat", "description": "AI 어시스턴트 — 학급 단위 통계 기반 자연어 응답 (PII 마스킹)."},
    {"name": "my", "description": "현재 사용자 본인 관점 조회 (학생/학부모 read-only)."},
    {"name": "health", "description": "운영 헬스체크 — liveness(/health) / readiness(/ready). 무중단 배포 게이트."},
]

DESCRIPTION = """
학생 성적·상담 관리 SaaS의 백엔드 API.

**계약 우선(contract-first)**: 모든 엔드포인트는 Pydantic v2 스키마로 정의되며,
이 문서(`/openapi.json`)가 프론트엔드·백엔드 간 단일 API 합의안이다.
`scripts/export_openapi.py`로 산출물을 추출해 팀 리뷰/Postman 임포트에 사용한다.

- **에러 계약**: 모든 비즈니스 에러는 `{ detail, code }` JSON (AppException)
- **인증**: JWT access(1h) / refresh(7d, HttpOnly). 모든 쿼리에 `role + school_id` 범위 강제
- **멀티테넌트 격리**: Postgres Row-Level Security로 DB 레벨에서 school_id 강제
"""

app = FastAPI(
    title="Student Manager API",
    version="0.1.0",
    description=DESCRIPTION,
    openapi_tags=tags_metadata,
    contact={"name": "정동현 (DongHyun Jung)", "email": "nawadri999@gmail.com"},
    license_info={"name": "Academic project — SW Design 최종 과제"},
)

# Rate limiting
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


@app.exception_handler(RateLimitExceeded)
async def ratelimit_handler(request: Request, exc: RateLimitExceeded):
    response = JSONResponse(
        status_code=429,
        content={
            "detail": "요청이 너무 잦습니다. 잠시 후 다시 시도하세요.",
            "code": "RATE_LIMITED",
        },
    )
    # slowapi의 limit 정보로 X-RateLimit-* 헤더 주입, 거기서 Retry-After 도출.
    view_limit = getattr(request.state, "view_rate_limit", None)
    if view_limit is not None:
        try:
            response = limiter._inject_headers(response, view_limit)
            reset = response.headers.get("X-RateLimit-Reset")
            if reset and "Retry-After" not in response.headers:
                import time
                retry = max(int(float(reset) - time.time()), 1)
                response.headers["Retry-After"] = str(retry)
        except Exception:
            response.headers.setdefault("Retry-After", "60")
    response.headers.setdefault("Retry-After", "60")
    return response


@app.get("/health", tags=["health"], summary="Liveness probe")
async def health_check():
    """프로세스 생존만 확인 (DB 미접근). 무중단 배포 시 컨테이너 재시작 판단용."""
    return {"status": "ok"}


@app.get("/ready", tags=["health"], summary="Readiness probe")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive operational guard
        raise AppException(503, "데이터베이스 준비가 되지 않았습니다.", "DB_NOT_READY") from exc
    return {"status": "ok", "database": "ok"}


# Routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(semesters.router, prefix="/api/v1")
app.include_router(classes.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(feedbacks.router, prefix="/api/v1")
app.include_router(grades.router, prefix="/api/v1")
app.include_router(counselings.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(students.router, prefix="/api/v1")
app.include_router(imports.router, prefix="/api/v1")
app.include_router(my.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
