# System Architecture — Student Manager

**버전**: 1.1 (v2.1 인프라 기준)
**작성일**: 2026-05-03
**기반 문서**: PRD v2.1, Design Spec v2.1, ADR-001 (재작성), ADR-002 (CDC — Outbox + Kafka)
**프로젝트 성격**: 졸업 평가용 로컬 프로토타입. 운영 사용자 0명. 평가 마감 2026-07-03 / 라이브 데모 + 발표.

---

## 1. 목적

이 문서는 PRD/Design Spec에 흩어진 인프라·런타임·데이터 흐름·확장성 관점을 단일 시점에서 설명한다. 코드 작업을 시작하기 전에 **모듈 간 입출력 계약**과 **병목·확장 한계**를 검증하기 위한 기준 문서.

본 v1.1은 다음 인프라 결정을 반영한다 (자세한 근거는 ADR-001/002 참조):
- 클라우드(EKS/Vercel/Render) 미도입 — 로컬 docker-compose
- LISTEN/NOTIFY ETL 폐기 — Outbox + Kafka KRaft 기반 CDC
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
                     (OpenAI 또는 Anthropic, 단일 선택)
```

> SMTP·Vercel Edge 등 외부 서비스는 평가용 로컬 환경에서 stub 또는 미연결 상태.

---

## 3. 컨테이너 다이어그램 (C4 Level 2)

모든 서비스는 단일 `docker-compose.yml`로 묶인다. 외부 의존성은 LLM Provider 1곳뿐.

```
┌──────────────────────────────────────────────────────────────────────┐
│  Browser                                                              │
└──────────────┬───────────────────────────────────────────────────────┘
               │ HTTP (dev) / HTTPS (옵션)
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  docker-compose (로컬)                                                │
│                                                                       │
│  ┌──────────────────────┐                                             │
│  │ frontend (Vite dev)  │  React 18 + TS, TanStack Query, Recharts    │
│  └──────────┬───────────┘                                             │
│             │ /api/v1                                                 │
│             ▼                                                         │
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
│     │ poll WHERE sent_at NULL │ UPSERT analytics.agg_*                │
│     ▼                        │                                        │
│  ┌──────────────────┐        │                                        │
│  │ outbox-publisher │        │                                        │
│  │ (aiokafka prod.) │        │                                        │
│  └────────┬─────────┘        │                                        │
│           │ produce           │                                       │
│           ▼                   │                                       │
│  ┌──────────────────┐         │                                       │
│  │ kafka (KRaft)    │  Fallback: redpanda (API 호환)                  │
│  │ topics:          │                                                 │
│  │  grade_events    │                                                 │
│  │  attendance_events                                                 │
│  │  feedback_events                                                   │
│  │  counseling_events                                                 │
│  └────────┬─────────┘                                                 │
│           │ consume                                                   │
│           ▼                                                           │
│  ┌──────────────────────────────────────────┐                         │
│  │ analytics-worker                         │  scale=N (consumer group)│
│  │ (aiokafka consumer + topic dispatch)     │                         │
│  │  ├─ fact_*_event INSERT ON CONFLICT       (idempotent on event_id) │
│  │  ├─ agg_student_* UPSERT                                           │
│  │  └─ dead_letter_event ← poison messages   (offset committed)       │
│  └──────────────────────────────────────────┘                         │
└──────────────────────────────────────────────────────────────────────┘
```

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
                    outbox-publisher          kafka          analytics-worker     Postgres
                          │                     │                 │                  │
                          │ SELECT WHERE sent_at IS NULL          │                  │
                          ├───────────────────────────────────────┼─────────────────►│
                          │ producer.send_and_wait('grade_events', payload)          │
                          ├────────────────────►│                 │                  │
                          │ UPDATE outbox SET sent_at=now()       │                  │
                          ├───────────────────────────────────────┼─────────────────►│
                                                │ consumer.poll() │                  │
                                                ├────────────────►│                  │
                                                │                 │ refresh_grade_aggregates(event)
                                                │                 │ - INSERT analytics.fact_grade_event
                                                │                 │ - UPSERT analytics.agg_student_subject
                                                │                 │ - UPSERT analytics.agg_student_overall
                                                │                 ├─────────────────►│
                                                │ commit offset   │                  │
                                                │◄────────────────┤                  │
```

핵심 일관성: **운영 트랜잭션과 outbox INSERT가 같은 트랜잭션** → broker 다운/publisher 다운 모두에서 이벤트 유실 0.

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
| outbox-publisher | Postgres | SQL (poll + UPDATE) | event row | poll 주기 0.5s |
| outbox-publisher | Kafka | producer.send_and_wait | bytes (JSON) | 발행까지 ≤ 1s (정상) |
| Kafka | analytics-worker | consumer poll (4 topics: grade/attendance/feedback/counseling) | bytes (JSON) | sub-second |
| analytics-worker | Postgres `analytics` | SQL INSERT ON CONFLICT + UPSERT | fact + agg row | best-effort, end-to-end ≤ 1분 |
| analytics-worker | Postgres `analytics.dead_letter_event` | SQL INSERT (poison message) | raw bytes + error | only on permanent failure |
| Browser | fastapi-api `/chat` | HTTP REST | { thread_id, message } | p95 ≤ 3s |
| fastapi-api | LLM Provider | HTTPS | masked context + prompt | timeout 10s |

---

## 5. 확장성 (Scalability)

평가 rubric의 "확장 가능한 설계" 정성 가점은 **다이어그램 + `docker-compose --scale` 라이브 시연**으로 입증한다. 클라우드 HPA·노드풀 자동 확장은 평가 후 트랙으로 미룬다.

### 5.1 수평 확장 가능 영역

| 컴포넌트 | 확장 방식 | 데모 방법 | 한계 |
|----------|-----------|-----------|------|
| fastapi-api | docker-compose `--scale fastapi-api=N` + 앞단 nginx (옵션) | n/a (운영 사용자 0) | DB connection pool |
| outbox-publisher | 단일 인스턴스 권장 (이중 발행 회피 위해 row-level lock 필요 시) | n/a | 단일 publisher가 충분 (평가 규모) |
| **analytics-worker** ★ | Kafka consumer group | `docker-compose up --scale analytics-worker=3` 라이브 시연 | 토픽 파티션 수 |
| Postgres | 단일 인스턴스 (평가 규모에서 충분) | n/a | 평가 후 read replica 분리 |

★ analytics-worker scale=N 시연이 발표의 "확장성" narrative 핵심.

### 5.2 단일 병목 (평가용 컨텍스트)

| 컴포넌트 | 병목 원인 | 평가용 한계 시점 | 평가 후 대응 |
|----------|-----------|-----------|------|
| Postgres | 단일 인스턴스 OLTP+OLAP+outbox 공존 | 평가 시드 데이터(수천 row) 내에선 무시 가능 | read replica + analytics 별도 인스턴스 분리 |
| Kafka KRaft 단일 노드 | 단일 broker | 평가 환경에서 무시 | 멀티 브로커 클러스터 |
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
| B2 | **Outbox 이벤트 미발행** | publisher 다운 중 운영 트랜잭션 commit | outbox row가 commit되어 있음 → 부팅 시 `WHERE sent_at IS NULL` 자동 catch-up | publisher 이중화 + leader election |
| B3 | Kafka broker 다운 | 단일 노드 KRaft 장애 | 운영 트랜잭션은 정상 commit (outbox row 누적). publisher가 broker 복구 후 재시도 | 멀티 브로커 클러스터 또는 Redpanda |
| B4 | Consumer 처리 지연 | 이벤트 쌓임 | `--scale analytics-worker=N`으로 수평 확장 | 파티션 수 증가 + worker 자동 확장 |
| B5 | 분석 쿼리 OLTP 영향 | 대시보드 쿼리 복잡화 | `agg_*` 사전 집계로 회피 | Read replica routing |
| B6 | 차트 렌더링 (FE) | 학생 수 ×과목 수 큰 경우 | 가상화 + memoization | WebWorker 오프로딩 |
| B7 | LLM 응답 지연 | 컨텍스트 큰 호출 | 응답 토큰 1024 상한 | Streaming response (SSE) |
| B8 | CSV import 동기 처리 | 대용량(>1000 row) 업로드 | 청크 분할 클라이언트 처리 | 백그라운드 Job |

### 6.2 측정·모니터링 포인트 (평가용)

평가용 환경에서는 PagerDuty·Slack 연동 없이 **로그 + 통합 테스트 + scale 시연 영상**으로 대체.

| 메트릭 | 검증 방법 |
|--------|-----------|
| 운영 변경 → 분석 반영 ≤ 1분 (REQ-074) | E2E 테스트 (Playwright) + testcontainers Kafka |
| Outbox publisher catch-up 동작 | 통합 테스트: publisher 강제 종료 → 운영 트랜잭션 N건 → 재기동 → 모두 발행 검증 |
| Consumer scale=3 정상 동작 | 라이브 데모: `docker-compose up --scale analytics-worker=3` + 메시지 분산 확인 |
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

---

## 8. 배포 / 실행 (로컬 평가)

```
git clone ...
make up                  # docker-compose up -d --build
make seed                # scripts/demo_seed.py 실행
make test                # ruff + pytest + tsc + playwright
make demo-scale          # docker-compose up --scale analytics-worker=3
```

| 환경 | 용도 |
|------|------|
| local-dev | 일상 개발. `docker-compose.yml` |
| local-demo | 발표 시연. `docker-compose.demo.yml` (시드 + scale 옵션) |

**롤백**: 평가 환경에서는 `docker-compose down -v && make up`. DB 마이그레이션은 평가 종료까지 forward-only.

---

## 9. 마이그레이션 / 백필

### 9.1 분석 스키마 + Outbox 도입 (v2.1)

1. Alembic revision 1: `analytics` 스키마 + 테이블 생성
2. Alembic revision 2: `public.outbox` 테이블 + 인덱스 생성
3. 운영 라우터에 outbox INSERT 코드 추가 (도메인 변경과 같은 트랜잭션)
4. 백필 스크립트 (`scripts/backfill_analytics.py`):
   - 운영 테이블 전체 스캔 → `public.outbox`에 INSERT (publisher가 정상 흐름으로 catch-up)
   - 또는 `analytics.fact_*`에 직접 INSERT + `analytics.agg_*` UPSERT (대량 백필 시)
5. publisher + analytics-worker 부팅 → catch-up 진행 확인
6. 정합성 검증 (`scripts/check_consistency.py`): 운영 row count vs `analytics.fact_*` count

### 9.2 기존 데이터에 영향 없음

운영 스키마(`public`) 도메인 테이블은 변경 없음. `public.outbox` 테이블만 신규 추가. 기존 트랜잭션 영향 ≤ 5ms (outbox INSERT 한 번 추가).

---

## 10. 추후 고려 (평가 후)

| 항목 | 트리거 | 후보 기술 |
|------|--------|-----------|
| Read replica 분리 | 운영 영향 발생 시 | Postgres physical replication + analytics routing |
| Kafka 멀티 브로커 / Connect | 실사용 단계 | Kafka cluster + Debezium (outbox source) |
| OAuth / SSO | 학교 단위 도입 시 | Google Workspace / SAML |
| Realtime 알림 | 30초 폴링이 부족할 때 | SSE / WebSocket |
| 클라우드 배포 | 학교 운영 도입 시 | EKS·Fargate·Cloud Run 중 재평가 |
| 캐싱 레이어 | 대시보드 쿼리 부하 | Redis |
| 벡터 검색 (정식 RAG) | 챗봇 컨텍스트 정교화 | pgvector |

---

## 11. Open Questions

평가 전까지 결정된 사항:

| 이전 OQ | 상태 | 결정 |
|---------|------|------|
| OQ-101 Kafka 도입 여부 | **폐기** | 평가 전 Kafka 도입 확정 (ADR-001/002) |

평가 후 검토:

| # | 질문 | 결정 시점 |
|---|------|-----------|
| OQ-201 | Outbox publisher 이중화 (leader election) 필요성 | 실사용 부하 측정 후 |
| OQ-202 | analytics 스키마를 별도 인스턴스로 분리 시점 | OLTP latency 영향 측정 후 |
| OQ-203 | 챗봇 응답 캐싱 정규화 키 설계 | 챗봇 사용 패턴 측정 후 |
| OQ-204 | 학교 관리자 역할 도입 | 사용자 피드백 |

---

*Architecture v1.1 — 로컬 docker-compose + Outbox + Kafka 기반*
