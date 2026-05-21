# Student Manager

학생 성적·상담 통합 관리 웹앱. FastAPI 백엔드 + React/Vite 프론트엔드 + Kafka 기반 분석 파이프라인 + LLM 챗봇.

## Quick demo (5 min)

처음 보는 사람이 5분 안에 풀스택을 시연할 수 있는 경로입니다.

**준비물**: Docker Desktop (또는 OrbStack), 4 GB 이상 여유 RAM. Node/Python 직접 설치는 필요 없습니다 — 컨테이너 안에서 모두 돕니다.

```bash
# 1) 클론
git clone https://github.com/jdh4601/student-manager.git
cd student-manager

# 2) 데모용 풀스택 기동 (analytics-worker 3개로 분산 처리 시연 포함)
docker compose -f docker-compose.yml -f docker-compose.demo.yml \
    up -d --scale analytics-worker=3

# 3) 데모 시드 데이터 (학생 30 / 학기 6 / 성적 1440 / 피드백·상담 ~240)
docker compose exec backend python /scripts/demo_seed.py
```

| 단계 | 액션 | URL / 명령 |
|------|------|-----------|
| 1 | 로그인 | http://localhost:5173 → `demo-teacher@example.com` / `password123` |
| 2 | 분석 대시보드 | `/analytics` — 6학기 평균/분포 차트 (Recharts) |
| 3 | AI 비서에 질의 | `/chat` → "이번 학기 평균 좀 알려줘" |
| 4 | 분산 처리 시연 | 새 터미널에서 `make demo-scale-logs` — 3개 워커가 파티션 분산 소비 |
| 5 | 정리 | `make demo-scale-down` |

발표 시 상세 시나리오와 사고 대응:

- 25분 발표 아웃라인: [`docs/notes/presentation-outline.md`](docs/notes/presentation-outline.md)
- 리허설 체크리스트 (T-60 / T-30 / 직전 / 시연 / 사후): [`docs/notes/demo-rehearsal-checklist.md`](docs/notes/demo-rehearsal-checklist.md)
- 분산 처리 라이브 데모 가이드: [`docs/notes/demo-scale-script.md`](docs/notes/demo-scale-script.md)

## Quick Start (개발용)

`KAFKA_NUM_PARTITIONS=3`로 분석 파이프라인까지 한 번에 띄우는 단일 인스턴스 모드:

```bash
docker compose up --build
```

- 프론트엔드: `http://localhost:5173`
- 백엔드 / Swagger: `http://localhost:18000` / `http://localhost:18000/docs`
- Kafka (KRaft 단일 노드): 컨테이너 내부 `kafka:9092`, 호스트 `localhost:29092`
- 기본 교사 계정: `teacher@example.com` / `password123` (RBAC E2E용 `teacher2@example.com`도 시드됨)

로컬 QA 실행:

```bash
npm run qa
```

백엔드 `ruff` + `pytest`, 프론트엔드 `tsc --noEmit`을 순서대로 실행합니다.

## 인증

- 액세스 토큰은 브라우저 메모리, 리프레시 토큰은 `HttpOnly` 쿠키로 관리합니다.
- 회원가입은 초대 링크 기반입니다. 교사가 학생/학부모를 초대하면 `/signup?token=...` 링크가 생성됩니다.
- `AUTH_LINK_DELIVERY=stub`(기본값)은 개발용이며, 운영에서는 SMTP 설정이 필요합니다.

## 데이터 가져오기 / 내보내기

- 학생 일괄 등록: CSV 또는 XLSX 업로드
- 성적 일괄 등록: CSV 또는 XLSX 업로드
- 상담 상세 페이지에서 PDF 리포트 내보내기 지원

## CI/CD

`main` 브랜치에 push하면 CI(lint + test + typecheck) → CD(Vercel 프론트 + Render 백엔드) 순으로 자동 배포됩니다.

필요한 GitHub Secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `RENDER_API_KEY`, `RENDER_SERVICE_ID`
