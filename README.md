# Student Manager

학생 성적·상담 통합 관리 웹앱

## Quick Start

### 1) Docker Compose (추천)

레포 루트에서 다음을 실행합니다.

```bash
docker compose up --build
```

- 접속: FE `http://localhost:5173`, BE `http://localhost:8000`, Swagger `http://localhost:8000/docs`
- 기본 계정: `teacher@example.com` / `password123`

### 2) Docker로 백엔드만 실행 + 로컬 프런트엔드

```bash
# Backend (Docker)
cd backend
docker build -t student-manager-backend .
docker run --rm -p 8000:8000 \
  -v $(pwd)/test.db:/app/test.db \
  -e ALLOWED_ORIGINS='["http://localhost:5173"]' \
  student-manager-backend

# Frontend (Vite dev)
cd ../frontend
npm install
npm run dev
```

주의: `ALLOWED_ORIGINS`는 JSON 문자열이어야 합니다. 예) `'["http://localhost:5173"]'`

Postgres 사용 시(선택):

```bash
docker run --rm -p 8000:8000 \
  -e DATABASE_URL='postgresql+asyncpg://user:pass@host:5432/student_manager' \
  -e ALLOWED_ORIGINS='["http://localhost:5173"]' \
  student-manager-backend
```

## Docs

- PRD: `docs/prd.md`
- 구현 계획: `docs/superpowers/plans/2026-03-20-student-manager-full-implementation.md`
- 디자인 스펙: `docs/design-spec.md`
