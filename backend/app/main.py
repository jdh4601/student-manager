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



app = FastAPI(title="Student Manager API", version="0.1.0")

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


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/ready")
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
