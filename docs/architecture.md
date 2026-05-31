# System Architecture — Student Manager

**버전**: 1.3 (발표 보완 — 교사 OAuth, 무중단 배포 probe, OpenAPI 명세)
**작성일**: 2026-05-31 (v1.2 → 2026-05-23)
**기반 문서**: PRD v2.2, Design Spec v2.1, ADR-001 (재작성), ~~ADR-002 (Outbox + Kafka)~~ → **ADR-003** (Outbox + Postgres LISTEN/NOTIFY + SKIP LOCKED)
**v1.3 변경**: 교사 Google OAuth 흐름(§4.5, §7.2) · 무중단 배포 liveness/readiness probe + 예시 K8s 매니페스트(§8) · OpenAPI 명세 산출(§4.6)
**프로젝트 성격**: 졸업 평가용 프로토타입 (Render + Vercel 클라우드 배포 + 로컬 docker-compose). 운영 사용자 0명. 평가 마감 2026-07-03 / 라이브 데모 + 발표.

---

## 1. 목적

이 문서는 PRD/Design Spec에 흩어진 인프라·런타임·데이터 흐름·확장성 관점을 단일 시점에서 설명한다. 코드 작업을 시작하기 전에 **모듈 간 입출력 계약**과 **병목·확장 한계**를 검증하기 위한 기준 문서.

본 v1.2는 다음 인프라 결정을 반영한다 (자세한 근거는 ADR-001/003 참조):
- 운영 surface는 **Vercel(Frontend) + Render(API Web + Worker × 2) + Render Postgres**. 분산 demo·E2E 통합 테스트는 로컬 docker-compose에서 수행 (deployment topology §8)
- CDC 패턴: **Outbox + Postgres LISTEN/NOTIFY + `SELECT FOR UPDATE SKIP LOCKED`** (ADR-003). Kafka KRaft 의존성 제거 (ADR-002 supersede)
- 챗봇 마이크로서비스 분리 폐기 — FastAPI 단일 엔드포인트

---

## 2. 시스템 컨텍스트 (C4 Level 1)

```
┌────────────────────────────────────────────────────────────────┐
│  Actors                                                        │
│  ├─ Teacher (교사)    : 성적·상담·피드백 입력, 분석 조회     │
│  ├─ Student (학생)    : 본인 성적·피드백 조회                 │
│  └─ Parent (학부모)   : 자녀 성적·공개 피드백 조회            │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  Student Manager (this system)                                 │
│  ─────────────────────────────────────────────────────────     │
│  - 학생 성적·출결·피드백·상담 관리                             │
│  - 분석 대시보드 (교사 전용)                                   │
│  - AI 어시스턴트 (교사 전용, 데모)                             │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                     [LLM Provider 외부]
                     (OpenAI 호환 endpoint, 단일)
```

> SMTP·Vercel Edge 등 외부 서비스는 평가용 로컬 환경에서 stub 또는 미연결 상태.

---

## 3. 컨테이너 다이어그램 (C4 Level 2)

서비스 구성은 dev/prod 모두 동일하며 로컬 docker-compose / 클라우드 Render 두 환경에서 동등하게 실행된다. 외부 의존성은 LLM Provider 1곳뿐 — **메시지 브로커는 Postgres 자체** (별도 Kafka/RabbitMQ 인프라 없음).

```
┌──────────────────────────────────────────────────────────────────────┐
│  Browser                                                              │
└──────────────┬───────────────────────────────────────────────────────┘
               │ HTTPS (Vercel 정적 호스팅 / dev: Vite)
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Vercel (Frontend)                                                    │
│  React 18 + TS · TanStack Query · Recharts                            │
└──────────────┬───────────────────────────────────────────────────────┘
               │ /api/v1
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Render (Backend Web + 2 Workers) ─ 또는 로컬 docker-compose 동등 토폴로지│
│                                                                       │
│  ┌─────────────────────────────────────────────────┐                  │
│  │ fastapi-api                                     │                  │
│  │  - 운영 라우터 (auth, grades, attendance, ...) │                  │
│  │  - /api/v1/analytics/*  (read agg)             │                  │
│  │  - /api/v1/chat         (LLM 호출, 단일 엔드)  │                  │
│  └──┬──────────────┬──────────────────┬──────────┬─┘                  │
│     │ SQL          │ outbox INSERT    │ SQL read │ HTTPS              │
│     ▼              ▼                  ▼          │                    │
│  ┌──────────────────────────────────┐            ▼                    │
│  │ postgres                         │      [LLM Provider 외부]        │
│  │  ├─ public.*       (OLTP)        │                                 │
│  │  ├─ public.outbox  (CDC source)  │                                 │
│  │  └─ analytics.*    (OLAP)        │                                 │
│  └──┬───────────────────────▲───────┘                                 │
│     │ SKIP LOCKED FETCH      │ SKIP LOCKED CLAIM + UPSERT             │
│     │ + pg_notify(<topic>)   │ + UPDATE outbox.processed_at           │
│     ▼                        │                                        │
│  ┌──────────────────┐        │                                        │
│  │ outbox-publisher │        │                                        │
│  │ (single, relay)  │        │                                        │
│  │  SELECT FOR UPDATE SKIP LOCKED → pg_notify → UPDATE sent_at        │
│  └────────┬─────────┘        │                                        │
│           │ NOTIFY            │                                       │
│           │ channels:         │                                       │
│           │  grade_events     │                                       │
│           │  attendance_events│                                       │
│           │  feedback_events  │                                       │
│           │  counseling_events│                                       │
│           ▼                   │                                       │
│  ┌──────────────────────────────────────────┐                         │
│  │ analytics-worker                         │  scale=N                │
│  │ (asyncpg LISTEN + SKIP LOCKED claim)     │  (SKIP LOCKED 분배)     │
│  │  ├─ on NOTIFY → claim outbox row by event_id                      │
│  │  ├─ INSERT ON CONFLICT analytics.fact_*  (idempotent on event_id) │
│  │  ├─ UPSERT agg_student_*                                          │
│  │  ├─ UPDATE outbox.processed_at = now()                            │
│  │  ├─ catch-up: 60s 폴링 WHERE processed_at IS NULL (NOTIFY 유실 보완)│
│  │  └─ dead_letter_event ← N회 retry 후 poison 격리 (processed_at 마킹)│
│  └──────────────────────────────────────────┘                         │
└──────────────────────────────────────────────────────────────────────┘
```

**scale=N 의미론**: Kafka consumer group의 partition 분배 대신 Postgres `SELECT ... FOR UPDATE SKIP LOCKED`로 worker가 outbox row 경쟁. N개 워커가 동일 NOTIFY를 받지만 정확히 1개만 row를 잠그고 처리. Sidekiq / oban 등 production 큐 시스템이 동일한 패턴 사용.

---

## 4. 모듈 간 데이터 흐름

### 4.1 운영 흐름 (성적 입력 예시)

```
Teacher Browser                fastapi-api               Postgres
     │                             │                        │
     │ PUT /grades/{id}            │                        │
     │ + JWT (access_token)        │                        │
     ├────────────────────────────►│                        │
     │                             │ 1. JWT 검증            │
     │                             │ 2. school_id+class 스코프 검증
     │                             │ 3. score 유효성 (0~100)
     │                             │ 4. grade_rank 계산
     │                             │ ┌──── 같은 트랜잭션 ───┐
     │                             │ │ 5. UPSERT public.grades
     │                             │ │ 6. INSERT public.outbox (topic='grade_events',
     │                             │ │       payload={grade_id, student_id, ...})
     │                             │ │ 7. INSERT public.notifications (preference 적용 후)
     │                             │ └─────────── COMMIT ───┘
     │                             ├───────────────────────►│
     │                             │ 200 + Grade 객체       │
     │◄────────────────────────────┤                        │
     │ Optimistic UI 확정          │                        │

(병렬, 비동기)
                    outbox-publisher                  analytics-worker × N      Postgres
                          │                                  │                     │
                          │ BEGIN; SELECT FOR UPDATE SKIP LOCKED                   │
                          │   WHERE sent_at IS NULL ORDER BY event_id LIMIT 100   │
                          ├──────────────────────────────────┼────────────────────►│
                          │ SELECT pg_notify('grade_events', '{"event_id":...}')   │
                          ├──────────────────────────────────┼────────────────────►│
                          │ UPDATE outbox SET sent_at = now() WHERE event_id IN (...) │
                          │ COMMIT;                                                │
                          ├──────────────────────────────────┼────────────────────►│
                                                             │ on_notify(channel, payload)
                                                             │ BEGIN; SELECT FOR UPDATE SKIP LOCKED
                                                             │   WHERE event_id = X AND processed_at IS NULL
                                                             │ ── only 1 of N workers wins the row ──
                                                             ├────────────────────►│
                                                             │ INSERT ON CONFLICT analytics.fact_grade_event
                                                             │ UPSERT analytics.agg_student_subject
                                                             │ UPSERT analytics.agg_student_overall
                                                             │ UPDATE outbox SET processed_at = now()
                                                             │ COMMIT;
                                                             ├────────────────────►│
```

핵심 일관성: **운영 트랜잭션과 outbox INSERT가 같은 트랜잭션** → publisher 다운/NOTIFY 유실 모두에서 이벤트 유실 0. NOTIFY가 유실되어도 catch-up 폴링(60s)이 `WHERE processed_at IS NULL` 잔여분을 자동 처리.

### 4.2 분석 조회 흐름

```
Teacher Browser                fastapi-api          analytics 스키마
     │ GET /analytics/teachers/me/dashboard          │
     ├────────────────────────────►│                 │
     │                             │ RBAC: 담당 학급 ID 목록
     │                             │ SELECT FROM analytics.agg_student_overall
     │                             │   WHERE student_id IN (...)
     │                             ├────────────────►│
     │                             │ 즉시 응답 (집계 캐시 read)
     │                             │ ◄───────────────┤
     │ ◄───────────────────────────┤
```

### 4.3 챗봇 흐름

```
Teacher                fastapi-api : routers/chat.py     analytics 스키마      LLM Provider
   │ POST /api/v1/chat      │                                │                    │
   ├───────────────────────►│                                │                    │
   │                        │ 1. RBAC 검증 (teacher only)    │                    │
   │                        │ 2. 의도 분류 (rule)            │                    │
   │                        │ 3. SELECT analytics.agg_* (학급 단위, k≥5)         │
   │                        ├───────────────────────────────►│                    │
   │                        │ ◄──────────────────────────────┤                    │
   │                        │ 4. sanitizer: 학생명·번호 → 학생A/seq_001          │
   │                        │ 5. SDK 직접 호출 (provider 1개)                    │
   │                        ├──────────────────────────────────────────────────►│
   │                        │ ◄──────────────────────────────────────────────────┤
   │                        │ 6. 응답 token → 실제 학생 매핑 (서버 메모리)      │
   │ ◄──────────────────────┤                                                    │
```

### 4.4 모듈 간 계약 요약

| Source | Target | Channel | Payload | SLA |
|--------|--------|---------|---------|-----|
| Browser | fastapi-api | HTTP REST | JSON (Pydantic schema) | p95 ≤ 500ms |
| fastapi-api | Postgres `public` | SQL (asyncpg) | SQLAlchemy 모델 | p95 ≤ 50ms |
| fastapi-api | Postgres `public.outbox` | SQL INSERT (같은 TX) | JSON payload | latency 영향 ≤ 5ms |
| outbox-publisher | Postgres `public.outbox` | SQL SELECT FOR UPDATE SKIP LOCKED + UPDATE | event row (batch ≤ 100) | poll 주기 0.5s |
| outbox-publisher | Postgres (NOTIFY) | `SELECT pg_notify(<channel>, <envelope>)` | JSON `{event_id}` (≤ 8KB) | 발행까지 ≤ 10ms |
| Postgres (NOTIFY) | analytics-worker | asyncpg `add_listener` 4 channels (grade/attendance/feedback/counseling) | JSON envelope | sub-second |
| analytics-worker | Postgres `public.outbox` | SELECT FOR UPDATE SKIP LOCKED (claim by event_id) | outbox row | per-event ≤ 50ms |
| analytics-worker | Postgres `analytics` | SQL INSERT ON CONFLICT + UPSERT | fact + agg row | best-effort, end-to-end ≤ 1분 |
| analytics-worker | Postgres `analytics.dead_letter_event` | SQL INSERT (poison message + outbox_event_id) | raw bytes + error | only after `OUTBOX_MAX_RETRIES` (기본 3) |
| Browser | fastapi-api `/chat` | HTTP REST | { thread_id, message } | p95 ≤ 3s |
| fastapi-api | LLM Provider | HTTPS | masked context + prompt | timeout 10s |
| Browser | fastapi-api `/auth/oauth/google/*` | HTTP REST | authorize_url / { code, state } | p95 ≤ 500ms |
| fastapi-api | Google OAuth/OIDC | HTTPS | code→token, userinfo | timeout 10s |

### 4.5 교사 Google OAuth 흐름 (v1.3, REQ-006)

```
Teacher Browser          fastapi-api : routers/auth.py        Google OAuth/OIDC
   │ GET /auth/oauth/google/login    │                              │
   ├────────────────────────────────►│ secrets.token → state        │
   │                                 │ Set-Cookie: oauth_state       │
   │                                 │   (HttpOnly, SameSite=lax,600s)│
   │ ◄── { authorize_url } ──────────┤                              │
   │ window.location = authorize_url │                              │
   ├────────────────────────────────┼─────────────────────────────►│ 사용자 동의
   │ ◄── redirect ?code=&state= ─────┼──────────────────────────────┤
   │ GET /auth/oauth/google/callback?code=&state=                   │
   ├────────────────────────────────►│ 1. state ↔ 쿠키 compare_digest│
   │                                 │    불일치 → 400 STATE_MISMATCH │
   │                                 │ 2. delete oauth_state cookie  │
   │                                 │ 3. code→token→userinfo        │
   │                                 ├──────────────────────────────►│
   │                                 │ ◄── { email, email_verified } ┤
   │                                 │ 4. email_verified 가드        │
   │                                 │ 5. 도메인 화이트리스트 게이트  │
   │                                 │    미허용 → 403 DOMAIN_NOT_ALLOWED
   │                                 │ 6. 기존 교사 로그인 / 신규 생성 │
   │                                 │    (oauth_default_school_id)   │
   │ ◄── TokenResponse (JWT) ────────┤                              │
```

**보안 결정**:
- **state CSRF 방어**: 발급한 state를 HttpOnly 쿠키에 바인딩, 콜백에서 `secrets.compare_digest`로 비교 (타이밍 공격 무력화). 불일치/누락 → `AUTH_OAUTH_STATE_MISMATCH` 400
- **stub provider 우회 차단**: `OAUTH_PROVIDER=auto`는 `GOOGLE_CLIENT_ID` 설정 시 real, 아니면 stub. stub은 `ENVIRONMENT≠production` 또는 `ALLOW_OAUTH_STUB=true`에서만 동작 — production에서 stub 호출 시 503 `AUTH_OAUTH_NOT_CONFIGURED`로 토큰 발급 거부
- **DI 패턴**: `GoogleOAuthClient` Protocol + `StubGoogleOAuthClient`/`RealGoogleOAuthClient` (LLM 클라이언트와 동일한 의도적 진화). 테스트는 stub으로 결정론적 검증 (`backend/tests/test_oauth.py` 8 cases)

### 4.6 API 명세 산출 (v1.3)

- FastAPI OpenAPI 3.1 자동 생성 + `tags_metadata`(14 그룹 설명)·license·contact 메타데이터 (`app/main.py`)
- 대화형 문서: Swagger UI `/docs`, ReDoc `/redoc`
- `scripts/export_openapi.py`가 `app.openapi()`를 `docs/api/openapi.json`으로 덤프 (53 paths / 53 schemas) — Postman 임포트·클라이언트 코드 생성용

---

## 5. 확장성 (Scalability)

평가 rubric의 "확장 가능한 설계" 정성 가점은 **다이어그램 + `docker-compose --scale` 라이브 시연**으로 입증한다. 클라우드 HPA·노드풀 자동 확장은 평가 후 트랙으로 미룬다.

### 5.1 수평 확장 가능 영역

| 컴포넌트 | 확장 방식 | 데모 방법 | 한계 |
|----------|-----------|-----------|------|
| fastapi-api | docker-compose `--scale fastapi-api=N` + 앞단 nginx (옵션) | n/a (운영 사용자 0) | DB connection pool |
| outbox-publisher | 단일 인스턴스가 기본. SKIP LOCKED 덕분에 다중 인스턴스도 안전 (이중 NOTIFY는 worker 측 SKIP LOCKED가 흡수) | n/a | 단일 publisher가 충분 (평가 규모) |
| **analytics-worker** ★ | `SELECT FOR UPDATE SKIP LOCKED` 기반 cooperative claim | `docker-compose up --scale analytics-worker=3` 라이브 시연 — N개 워커가 동일 NOTIFY를 받지만 row lock으로 정확히 1개만 처리 | DB row-lock 경쟁 (평가 규모 ms 단위 무시 가능) |
| Postgres | 단일 인스턴스 (평가 규모에서 충분) | n/a | 평가 후 read replica 분리 |

★ analytics-worker scale=N 시연이 발표의 "확장성" narrative 핵심. **SKIP LOCKED 패턴 = Kafka consumer group 등가물** (production 사례: Sidekiq `bulk_dequeue`, oban `Oban.Job`).

### 5.2 단일 병목 (평가용 컨텍스트)

| 컴포넌트 | 병목 원인 | 평가용 한계 시점 | 평가 후 대응 |
|----------|-----------|-----------|------|
| Postgres | 단일 인스턴스 OLTP+OLAP+outbox+NOTIFY backplane 공존 | 평가 시드 데이터(수천 row) 내에선 무시 가능 | read replica + analytics 별도 인스턴스 분리 |
| NOTIFY 채널 단일 backplane | Postgres NOTIFY는 인스턴스 글로벌 큐 | 평가 환경에서 무시 (qps 낮음) | 토픽 sharding 또는 외부 broker 도입 |
| LLM provider rate limit | 외부 의존 | 분당 10회 rate limit으로 보호 | 캐싱·streaming |

### 5.3 데이터 볼륨 가정 (평가용)

평가 환경에서는 시드 데이터 기준 학생 수십~수백 명 규모. 운영 환경 가정값(수만 row)은 설계 의도로만 유지하고 실제 측정은 평가 후 수행.

| 엔티티 | 평가용 시드 | 운영 환경 가정 (참고) |
|--------|-------------|------------------------|
| Student | ~30 | 학교당 ~500 |
| Grade | ~1,800 | 학교당 ~30,000 |
| Attendance | ~6,000 | 학교당 ~100,000 |
| analytics.fact_grade_event | ~1,800 | 학교당 ~30,000 |

---

## 6. 병목 (Bottlenecks) & 대응

### 6.1 식별된 병목

| # | 병목 | 발현 조건 | 1차 대응 | 평가 후 대응 |
|---|------|-----------|----------|----------------|
| B1 | DB connection 고갈 | API replica × 풀 크기 | 평가용에선 무시. pool size 명시 | pgBouncer (transaction pool) |
| B2 | **Outbox 이벤트 미발행** | publisher 다운 중 운영 트랜잭션 commit | outbox row가 commit되어 있음 → 부팅 시 `WHERE sent_at IS NULL` 자동 catch-up | publisher 이중화 (SKIP LOCKED로 race-free) |
| B3 | LISTEN connection 끊김 → NOTIFY 유실 | Render free Postgres connection limit / network blip | worker의 60s catch-up 폴링이 `WHERE processed_at IS NULL` 잔여분 처리. connection 재시도 (exponential backoff) | 멀티 인스턴스 worker + PgBouncer |
| B4 | Worker 처리 지연 | 이벤트 쌓임 | `--scale analytics-worker=N`으로 수평 확장 (SKIP LOCKED로 작업 분배) | worker 자동 확장 |
| B5 | 분석 쿼리 OLTP 영향 | 대시보드 쿼리 복잡화 | `agg_*` 사전 집계로 회피 | Read replica routing |
| B6 | 차트 렌더링 (FE) | 학생 수 ×과목 수 큰 경우 | 가상화 + memoization | WebWorker 오프로딩 |
| B7 | LLM 응답 지연 | 컨텍스트 큰 호출 | 응답 토큰 1024 상한 | Streaming response (SSE) |
| B8 | CSV import 동기 처리 | 대용량(>1000 row) 업로드 | 청크 분할 클라이언트 처리 | 백그라운드 Job |

### 6.2 측정·모니터링 포인트 (평가용)

평가용 환경에서는 PagerDuty·Slack 연동 없이 **로그 + 통합 테스트 + scale 시연 영상**으로 대체.

| 메트릭 | 검증 방법 |
|--------|-----------|
| 운영 변경 → 분석 반영 ≤ 1분 (REQ-074) | E2E 테스트 (Playwright) + testcontainers Postgres |
| Outbox publisher catch-up 동작 | 통합 테스트: publisher 강제 종료 → 운영 트랜잭션 N건 → 재기동 → 모두 발행 검증 |
| Worker scale=3 정상 동작 (SKIP LOCKED) | 라이브 데모: `docker-compose up --scale analytics-worker=3` + 동일 outbox row가 정확히 1개 워커에서만 처리됨 확인 |
| API p95 ≤ 500ms (NFR) | locust 또는 k6 로컬 부하 (옵션) |

---

## 7. 보안 경계

```
[Browser]
        │ HTTP (로컬 dev) / HTTPS (선택)
        ▼
[fastapi-api]
        │ asyncpg
        ▼
[Postgres (docker-compose 내부)]
```

평가용 로컬 환경이므로 클러스터 mTLS·ALB·SSL termination 등 클라우드 보안 경계는 적용하지 않는다. 운영 배포 시 추가는 평가 후 작업.

### 7.1 데이터 보안

| 데이터 | 저장 | 전송 | 로그 |
|--------|------|------|------|
| 비밀번호 | bcrypt (cost ≥ 12) | TLS (옵션) | 절대 출력 금지 |
| JWT access | 메모리 (Zustand) | Authorization 헤더 | 절대 출력 금지 |
| JWT refresh | HttpOnly Cookie (SameSite=Strict, Secure) | TLS (옵션) | 절대 출력 금지 |
| 학생 PII | DB 평문 (school_id 격리) | 로컬 | 로그 masking 필수 |
| LLM 컨텍스트 | (저장 안 함) | TLS | 마스킹된 token만 (`학생A`) |

### 7.2 RBAC 검증 위치

1. JWT 미들웨어 (FastAPI Depends): `role + school_id + user_id` 추출
2. 라우터 단계: 역할 화이트리스트 (`require_role(["teacher"])`)
3. 서비스 단계: row-level scope (`Class.teacher_id = current_user.id`)

> 교사 OAuth(REQ-006)로 발급된 JWT도 동일 RBAC 경로를 통과한다. OAuth는 **인증(authentication) 진입점**만 추가할 뿐, 인가(authorization) 경계는 위 3단계로 일원화 — 도메인 화이트리스트는 교사 계정 발급 시점의 게이트다 (§4.5).

---

## 8. 배포 / 실행 (Deployment Topology)

두 개의 deployment surface가 공존한다 — **클라우드는 외부 접근용 thin demo**, **로컬은 분산 컴포넌트 완전 시연**.

| 환경 | 용도 | 컴포넌트 |
|------|------|---------|
| **cloud (Vercel + Render)** | 외부 접근 가능한 라이브 demo URL | Vercel(Frontend) + Render(API Web) + Render(outbox-publisher worker) + Render(analytics-worker worker) + Render Postgres |
| **local-dev (docker-compose.yml)** | 일상 개발 | 위 5개 컴포넌트 동등 + Vite dev server |
| **local-demo (docker-compose.demo.yml)** | 발표 시연 (scale 옵션 포함) | local-dev + 시드 데이터 + `--scale analytics-worker=3` |

```
# 로컬 (개발/시연)
git clone ...
make up                  # docker-compose up -d --build
make seed                # scripts/demo_seed.py 실행
make qa                  # ruff + pytest + tsc (Makefile 기준)
make e2e                 # playwright
make demo-scale          # docker-compose up --scale analytics-worker=3

# 클라우드 (Render + Vercel)
# render.yaml 기준 자동 배포 — main 브랜치 push 시 CD workflow가 트리거
# 배포 후 라이브 URL은 Render dashboard 확인
```

**왜 두 surface?**
- 클라우드 Render는 외부 reviewer가 발표 후 접속할 수 있는 라이브 URL 제공 (Vercel + Render free tier 활용)
- 로컬 docker-compose는 `--scale analytics-worker=3` 같은 분산 시연을 reviewer 앞에서 즉시 실행 가능 (Render free tier에서는 worker 다중 인스턴스 비용 + cold start 부담)
- 두 환경에서 동일 코드, 동일 컴포넌트 토폴로지, 동일 마이그레이션. 분기는 환경변수만 차이

**롤백**: 로컬은 `docker-compose down -v && make up`. 클라우드는 Render 이전 배포로 redeploy (Render dashboard 1-click). DB 마이그레이션은 평가 종료까지 forward-only.

### 8.1 무중단 배포 (Zero-Downtime, v1.3)

배포 중 503/끊김 없이 신버전으로 전환하기 위한 **헬스 게이트**를 구현했다.

| Probe | 엔드포인트 | 검증 | 실패 시 |
|-------|-----------|------|---------|
| **Liveness** | `GET /health` | 프로세스 생존 (즉시 200) | 컨테이너 재시작 |
| **Readiness** | `GET /ready` | `SELECT 1`로 DB 연결 확인 | 503 `DB_NOT_READY` → 트래픽 차단 (재시작 아님) |

핵심: **liveness ≠ readiness**. DB가 잠시 끊겨도 프로세스는 살아있으므로(liveness OK) 재시작하지 않고, readiness만 실패시켜 트래픽에서 일시 제외 → 복구 시 자동 재합류. 부팅 중 DB 미준비 상태에서 트래픽 수신을 막는다.

**롤링 시퀀스** (Render 자동 / 예시 K8s 동일 의미론):
```
신버전 Pod 기동 → /ready 통과 대기 → LB에 합류 → 구버전 트래픽 드레인 → 구버전 종료
```
- `deploy/k8s/backend-deployment.yaml`: `RollingUpdate maxUnavailable=0, maxSurge=1` + liveness/readiness probe (신 Pod ready 전까지 구 Pod 유지 → 가용 용량 0 구간 없음)
- `deploy/k8s/analytics-worker-deployment.yaml`: worker `replicas=3` (SKIP LOCKED 수평 확장 시연), publisher 단일
- **예시 매니페스트의 위치**: 운영 K8s 클러스터는 평가 후 트랙. 본 yaml은 커리큘럼의 "무중단 배포·롤링 업데이트" 개념을 **probe 구현 + 의도된 토폴로지**로 입증하기 위한 산출물이며, 실제 demo는 Render 롤링 재배포로 동등 시연 (`docs/notes/zero-downtime-deployment.md`)

---

## 9. 마이그레이션 / 백필

### 9.1 분석 스키마 + Outbox 도입 (v2.1) + LISTEN/NOTIFY 전환 (ADR-003)

1. Alembic revision 1: `analytics` 스키마 + 테이블 생성 (`0004_analytics_schema`)
2. Alembic revision 2: `public.outbox` 테이블 + 인덱스 생성 (`0005_outbox_table`)
3. 운영 라우터에 outbox INSERT 코드 추가 (도메인 변경과 같은 트랜잭션)
4. Alembic revision 3 (ADR-003): `public.outbox.processed_at` + `retry_count` + `last_error` 컬럼, `analytics.dead_letter_event.outbox_event_id` 컬럼 (`0009_outbox_processed_at`)
5. **백필 스크립트는 미구현 (평가 후 트랙)**. 평가용 시드는 `scripts/demo_seed.py`가 운영 INSERT와 함께 `public.outbox` row를 stage하므로 publisher/worker가 정상 흐름으로 채운다.
6. publisher + analytics-worker 부팅 → catch-up 진행 확인 (publisher: `WHERE sent_at IS NULL` 드레인, worker: `WHERE processed_at IS NULL` 드레인)
7. 정합성 검증: testcontainers Postgres 기반 통합 테스트 (`backend/tests/integration/*`, `pytest -m integration`)가 운영 row 수 vs `analytics.fact_*` row 수를 자동 비교. SKIP LOCKED scale=3 시 중복 처리 없음도 동일 테스트가 검증.

### 9.2 기존 데이터에 영향 없음

운영 스키마(`public`) 도메인 테이블은 변경 없음. `public.outbox` 테이블만 신규 추가. 기존 트랜잭션 영향 ≤ 5ms (outbox INSERT 한 번 추가).

---

## 10. 추후 고려 (평가 후)

| 항목 | 트리거 | 후보 기술 |
|------|--------|-----------|
| Read replica 분리 | 운영 영향 발생 시 | Postgres physical replication + analytics routing |
| 외부 message broker 도입 (Kafka/Redpanda/SQS) | NOTIFY backplane 한계 또는 cross-region 요구 | Debezium (outbox source) + 외부 broker |
| ~~OAuth / SSO~~ → **교사 Google OAuth 구현됨 (v1.3, §4.5)**. 학생·학부모 SSO·SAML은 평가 후 | 학교 단위 확대 시 | Google Workspace / SAML |
| Realtime 알림 | 30초 폴링이 부족할 때 | SSE / WebSocket |
| 클라우드 배포 | 학교 운영 도입 시 | EKS·Fargate·Cloud Run 중 재평가 |
| 캐싱 레이어 | 대시보드 쿼리 부하 | Redis |
| 벡터 검색 (정식 RAG) | 챗봇 컨텍스트 정교화 | pgvector |

---

## 11. Open Questions

평가 전까지 결정된 사항:

| 이전 OQ | 상태 | 결정 |
|---------|------|------|
| OQ-101 Kafka 도입 여부 | **폐기 → 재폐기** | 2026-05-03 도입 결정 (ADR-002) → 2026-05-23 도메인 규모 부적합으로 폐기 (ADR-003), LISTEN/NOTIFY로 전환 |
| OQ-102 클라우드 배포 surface | **결정** | Render(Backend Web + 2 Workers) + Vercel(Frontend) + Render Postgres. 분산 시연은 로컬 docker-compose 병행. |

평가 후 검토:

| # | 질문 | 결정 시점 |
|---|------|-----------|
| OQ-201 | Outbox publisher 이중화 필요성 | 실사용 부하 측정 후 (SKIP LOCKED로 race-free 다중화는 이미 지원) |
| OQ-202 | analytics 스키마를 별도 인스턴스로 분리 시점 | OLTP latency 영향 측정 후 |
| OQ-203 | 챗봇 응답 캐싱 정규화 키 설계 | 챗봇 사용 패턴 측정 후 |
| OQ-204 | 학교 관리자 역할 도입 | 사용자 피드백 |
| OQ-205 | NOTIFY backplane 한계 도달 시 외부 broker 도입 | qps + cross-region 요구 발생 시 |

---

*Architecture v1.3 — Vercel/Render 클라우드 + 로컬 docker-compose + Outbox + Postgres LISTEN/NOTIFY + 교사 OAuth + 무중단 배포 probe 기반*
