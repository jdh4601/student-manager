FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=on

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy source
COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY seed.py /app/seed.py
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

# Default to sqlite for local container runs
ENV DATABASE_URL=sqlite+aiosqlite:///./test.db \
    TEST_DATABASE_URL=sqlite+aiosqlite:///./test.db \
    SECRET_KEY=change-me-in-production \
    ALGORITHM=HS256 \
    ACCESS_TOKEN_EXPIRE_MINUTES=60 \
    REFRESH_TOKEN_EXPIRE_DAYS=7 \
    INVITE_TOKEN_EXPIRE_HOURS=72 \
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=60 \
    APP_BASE_URL=http://localhost:5173 \
    AUTH_LINK_DELIVERY=stub \
    RUN_SEED=0 \
    ALLOWED_ORIGINS="[\"https://frontend-phi-sand-33.vercel.app\"]"

EXPOSE 8000

CMD ["/app/docker-entrypoint.sh"]
