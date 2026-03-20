# Student Manager

중·고등학교 교사를 위한 학생 성적·상담 통합 관리 웹 플랫폼 (12주 대학 소프트웨어설계 개인 프로젝트)

## 기술 스택

| Frontend | Backend | Database |
|----------|---------|----------|
| React 18, TypeScript, Vite | FastAPI, Python 3.11 | PostgreSQL (Supabase) |
| Tailwind CSS, Zustand, TanStack Query | SQLAlchemy 2.0, Alembic, JWT | |

**배포**: Vercel (FE) + Render (BE) + Supabase (DB) — 전체 무료 티어

## 주요 기능

- **성적 관리**: 과목별 성적 입력, 총점/평균/9등급 자동 계산, 레이더 차트 시각화
- **학생부**: 학생 정보 CRUD, 출결 관리, 특기사항 기록
- **피드백**: 카테고리별 작성, 학생/학부모 공개 설정
- **상담**: 상담 기록 및 학교 내 교사 간 공유
- **알림**: 인앱 실시간 알림 (30초 폴링)
- **RBAC**: 교사 / 학생 / 학부모 역할별 권한 관리
- **내보내기**: Excel (SheetJS), PDF (jsPDF) 클라이언트 생성

## 시작하기

```bash
# Backend
cd backend
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 환경변수 설정
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
cp .env.example .env  # VITE_API_URL=http://localhost:8000
npm run dev
```

API 문서: http://localhost:8000/docs (Swagger UI)

## 테스트

```bash
# Backend
pytest -x -q

# Frontend
npm test
```

## 문서

- [PRD](docs/PRD.md) — 제품 요구사항
- [설계 명세서](docs/design-spec.md) — 상세 기술 설계
- [구현 계획](docs/superpowers/plans/2026-03-20-student-manager-full-implementation.md)

## 라이선스

MIT
