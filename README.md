# Student Manager

학생 성적·상담 통합 관리 웹앱. FastAPI 백엔드 + React/Vite 프론트엔드 + **Postgres LISTEN/NOTIFY 기반 이벤트 분석 파이프라인** + LLM 챗봇.

## 🌐 라이브 데모

| 항목 | URL | 비고 |
|------|-----|------|
| **앱 (Frontend)** | https://frontend-phi-sand-33.vercel.app | Vercel |
| **API / Swagger** | https://student-manager-backend-atmg.onrender.com/docs | Render |
| **데모 계정** | `teacher@example.com` / `password123` | 교사 권한 |

> Render free 인스턴스는 유휴 시 잠들어 **첫 요청이 ~50초** 걸릴 수 있습니다. 백엔드 `/docs`를 한 번 열어 깨운 뒤 로그인하세요.

## Deployment Topology

두 surface 모두 동일 컴포넌트 토폴로지·코드·마이그레이션을 사용한다 — 분기는 환경변수만 차이.

| Surface | 용도 | 구성 |
|---------|------|------|
| **Cloud** (Vercel + Render) | 외부 접근용 라이브 demo URL | Vercel(Frontend) + Render(Backend Web + outbox-publisher + analytics-worker×3) + Render Postgres |
| **Local** (docker-compose) | 일상 개발 + 분산 시연 (`--scale analytics-worker=N`) | 위 컴포넌트 동등 + Vite dev server (Kafka·외부 브로커 불필요 — Postgres NOTIFY를 message bus로) |

자세한 CDC 아키텍처: [`docs/architecture.md`](docs/architecture.md)

## Quick demo (5 min, 로컬)

**준비물**: Docker Desktop (또는 OrbStack), 4 GB+ 여유 RAM. Node/Python 직접 설치 불필요.

```bash
git clone https://github.com/jdh4601/student-manager.git
cd student-manager

# 데모용 풀스택 기동 (analytics-worker 3개로 SKIP LOCKED 분산 처리 시연)
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --scale analytics-worker=3

# 데모 시드 (학생 30 / 학기 6 / 성적 1440 / 피드백·상담 ~240)
docker compose exec backend python /scripts/demo_seed.py
```

| 단계 | 액션 | URL / 명령 |
|------|------|-----------|
| 1 | 로그인 | http://localhost:5173 → `demo-teacher@example.com` / `password123` |
| 2 | 분석 대시보드 | `/analytics` — 6학기 평균/분포 차트 (Recharts) |
| 3 | AI 비서 질의 | `/chat` → "이번 학기 평균 좀 알려줘" |
| 4 | 분산 처리 시연 | 새 터미널 `make demo-scale-logs` — 3개 워커가 SKIP LOCKED로 작업 분배 |
| 5 | 정리 | `make demo-scale-down` |

## Quick Start (개발용)

분석 파이프라인까지 한 번에 띄우는 단일 인스턴스 모드:

```bash
docker compose up --build
```

- 프론트엔드: `http://localhost:5173`
- 백엔드 / Swagger: `http://localhost:18000` / `http://localhost:18000/docs`
- Postgres: 호스트 `localhost:5432` (메시지 브로커 겸용 — `NOTIFY` 채널 4개)
- 기본 교사 계정: `teacher@example.com` / `password123` (RBAC E2E용 `teacher2@example.com`도 시드됨)

```bash
python scripts/listen_notify_smoke.py   # LISTEN/NOTIFY 회선 헬스 체크 (OK → exit 0)
npm run qa                              # ruff + pytest + tsc 순차 실행
```

## AI 챗봇 / LLM API 키

`/chat`의 AI 비서는 **OpenAI(호환) API**를 사용합니다. 키가 없으면 결정론적 stub으로 자동 폴백하므로 데모만 돌릴 땐 키 없이도 동작합니다.

`backend/.env`에 추가 (없으면 `backend/.env.example` 복사):

```bash
OPENAI_API_KEY=sk-...                # https://platform.openai.com/api-keys
LLM_BASE_URL=https://api.openai.com/v1   # 다른 OpenAI 호환 엔드포인트로 교체 가능
LLM_MODEL=gpt-4o-mini
LLM_PROVIDER=auto                    # auto: 키 있으면 OpenAI / 없으면 stub
```

다른 제공자는 `LLM_BASE_URL`·`LLM_MODEL`만 교체 (예: Moonshot `https://api.moonshot.ai/v1` / `moonshot-v1-8k`). 키 변경 후 `docker compose restart backend`.

> **보안**: `.env`는 커밋 금지(`.gitignore` 포함). API 키는 프론트엔드에 두지 않고 모든 LLM 호출은 백엔드 `/api/v1/chat`을 경유. 운영은 시크릿 매니저로 주입.

## 인증

- 액세스 토큰은 브라우저 메모리, 리프레시 토큰은 `HttpOnly` 쿠키로 관리.
- 교사 = Google OAuth + 학교 도메인 화이트리스트 / 학생·학부모 = 초대 링크 가입(`/signup?token=...`).
- 크로스사이트(Vercel↔Render) 배포 시 리프레시 쿠키는 `COOKIE_SAMESITE=none` + `COOKIE_SECURE=true` 필요.
- `AUTH_LINK_DELIVERY=stub`(기본)은 개발용 — 운영은 SMTP 설정 필요.

## 데이터 가져오기 / 내보내기

학생·성적 일괄 등록(CSV/XLSX 업로드), 상담 상세에서 PDF 리포트 내보내기.

## CI/CD

`main` push → CI(lint + test + typecheck) → CD(Vercel 프론트 + Render Web/Worker auto-deploy). Render는 `render.yaml`의 3개 서비스(web + outbox-publisher + analytics-worker)를 일괄 배포.

필요한 GitHub Secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `RENDER_API_KEY`, `RENDER_SERVICE_ID`
