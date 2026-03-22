from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.errors import AppException
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
    return JSONResponse(status_code=429, content={"detail": "Too Many Requests", "code": "RATE_LIMIT_EXCEEDED"})


@app.get("/health")
async def health_check():
    return {"status": "ok"}


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
