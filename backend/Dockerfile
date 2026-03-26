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

# Default to sqlite for local container runs
ENV DATABASE_URL=sqlite+aiosqlite:///./test.db \
    TEST_DATABASE_URL=sqlite+aiosqlite:///./test.db \
    SECRET_KEY=change-me-in-production \
    ALGORITHM=HS256 \
    ACCESS_TOKEN_EXPIRE_MINUTES=60 \
    REFRESH_TOKEN_EXPIRE_DAYS=7 \
    ALLOWED_ORIGINS="[\"http://localhost:5173\"]"

EXPOSE 8000

# Create tables and seed a demo teacher if missing
RUN python - <<'PY'
import asyncio
from seed import seed
asyncio.run(seed())
PY

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
