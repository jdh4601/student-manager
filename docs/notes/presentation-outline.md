# 발표 아웃라인 — Student Manager v2.2

**연관**: SMS-71 / Architecture v1.2 / ADR-002·003 / Phase 8
**구성**: 발표 15분 + 라이브 시연 10분
**발표 관점**: "기술 스택·아키텍처를 *왜* 이렇게 선택했는가"가 중심. 모든 결정은 하나의 메시지로 수렴 →
**도메인 규모(학교당 500명·성적 30k row, 분석은 학급 30명 단위)에 맞춘 right-sizing.**

> 깊은 근거는 `docs/architecture.md`(v1.2), `docs/decisions/002·003`을 Q&A 백업으로 둔다.

---

## 0. 한 줄 메시지 (thesis)

> 좋은 설계는 *최신* 기술이 아니라 **문제 규모에 맞는** 기술을 고르는 것.
> 우리는 Kafka로 결정해 구현까지 끝낸 뒤, 도메인 규모를 재평가해 Postgres LISTEN/NOTIFY로 **되돌렸고**(ADR-002 → 003),
> 그 판단이 배포(브로커·secret·비용 제거)까지 단순하게 만들었다.

발표 차별점: 대부분 "X를 골랐고 좋다"고 말한다. 우리는 **"결정 → 구현 → 재평가 → 번복"을 ADR로 문서화한 과정** 자체를 보여준다. (소프트웨어 설계 수업이 평가하는 건 최신 기술이 아니라 *판단 근거와 트레이드오프 이해*다.)

---

## 1. 문제 (2분)

- 한국 학교 교사는 성적·피드백·상담·알림을 4개의 분산된 도구(엑셀/문서/카톡/지필)에서 다룬다. 단일 학생 분석에 평균 8~12분.
- 학부모는 학기 종료 전엔 자녀의 학교 데이터에 거의 접근 불가.
- → 요구: **단일 SaaS + 실시간 분석 갱신 + 안전한 AI 비서**
- **규모를 먼저 못박는다 (이후 모든 결정의 근거)**: 학교당 학생 ~500, 성적 ~30k row, 분석은 학급(30명) 단위 조회. *고QPS·대용량 스트리밍 도메인이 아니다.* ← 이 한 줄이 아키텍처·배포 선택 전체를 정당화한다.

## 2. 솔루션 한 줄

> **SaaS형 학생 관리 + 이벤트 기반 실시간 분석 + PII-안전 AI 비서**

---

## 3. 아키텍처 개요 (3분)

```
[Vercel/React] ──HTTPS──▶ [FastAPI (Render Web)]
                            │  ├── INSERT public.outbox  (운영 변경과 같은 TX)
                            ▼  ▼
                          [Postgres (Render)]   ← OLTP + OLAP + CDC source + 메시지 backplane
                          ┌──────────────────┐
                          │ public.*  (OLTP) │
                          │ public.outbox    │
                          │ analytics.*(OLAP)│
                          └──┬───────────▲───┘
                             │ pg_notify  │ SKIP LOCKED claim + UPSERT
                             ▼            │ + UPDATE processed_at
              [outbox-publisher (Render Worker)]
                             │ NOTIFY 4 channels
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        analytics-w1   analytics-w2   analytics-w3   (scale=N, 로컬 시연)
              ── 모두 LISTEN, SKIP LOCKED로 row claim ──
                             ▼
                    [analytics.agg_*] ◀── 교사 대시보드 / 챗봇
```

- **3계층 + 단일 Postgres가 메시지 브로커까지 겸함**. 외부 의존성은 LLM provider 1곳뿐.
- **핵심 일관성 보장 (강조)**: 운영 변경(grade UPSERT)과 `public.outbox` INSERT가 **같은 트랜잭션** → publisher 다운/NOTIFY 유실 어느 경우에도 **이벤트 유실 0**. 유실 시 worker의 catch-up 폴링(60s)이 `WHERE processed_at IS NULL` 잔여분을 자동 처리. (Architecture §4.1)

---

## 4. 기술 스택 선택 이유 (3분) ★ 중점 ①

| 계층 | 선택 | 주요 대안 | **왜** |
|------|------|-----------|--------|
| FE 프레임워크 | **React 18 + Vite + TS** | Next.js | 교사 전용 대시보드라 **SSR/SEO 불필요** → Next.js 오버헤드 회피. Vite HMR 속도 + Vercel 호환 |
| FE 상태/시각화 | TanStack Query + Recharts | Redux + 직접 fetch | 서버 상태/클라이언트 상태 분리, 캐싱·재검증 자동화 |
| API | **FastAPI (async)** | Django / Flask | async I/O로 asyncpg 활용, Pydantic v2 입력검증, 자동 OpenAPI 문서, **단일 언어(Python)로 worker까지** |
| DB | **PostgreSQL 단일 인스턴스** | PG + 별도 OLAP/broker | OLTP(`public`) + OLAP(`analytics`) + CDC(`outbox`) + **메시지 backplane(NOTIFY)** 을 한 엔진에 → 인프라 최소화 |
| DB 드라이버 | **asyncpg** (+ Alembic은 psycopg2) | psycopg2 only | asyncpg는 **LISTEN/NOTIFY 네이티브** + async 지원. 마이그레이션만 동기 드라이버로 분리 |
| CDC / 메시지 | **Outbox + LISTEN/NOTIFY + SKIP LOCKED** | Kafka / Debezium | 도메인 규모에 broker는 over-engineered → §5에서 상세 |
| 인증 | **JWT (access=메모리 / refresh=HttpOnly Cookie)** | localStorage 토큰 | localStorage는 XSS에 노출 → 프로젝트 규칙상 금지. refresh는 HttpOnly + SameSite=Strict |
| LLM | **OpenAI 호환 SDK (단일 endpoint)** | provider별 SDK | `LLM_BASE_URL`만 바꾸면 Kimi/Moonshot 등 교체. 전송 전 **PII 마스킹 + k≥5 익명성** |

> 관통하는 원칙: **컴포넌트 수를 늘리지 않는다.** 새 인프라를 추가할 때마다 secret·모니터링·장애 표면이 늘어난다 → 규모가 정당화할 때까지 보류(YAGNI).

---

## 5. 아키텍처 의사결정: Kafka → LISTEN/NOTIFY (3분) ★ 중점 ② · 발표 하이라이트

**1차 결정 — ADR-002 (5/3): Outbox + Kafka KRaft 단일 노드 + aiokafka**
- 이유: rubric의 *"Kafka 같은 메시지 스트림"* 가점 + 이벤트 유실 방어(outbox commit → 부팅 catch-up)
- 대안 비교: Debezium(❌ 1인·미경험엔 critical path 위험), App-direct publish(❌ broker 다운 시 유실)
- **실제로 구현·통합테스트까지 완료** (`scripts/kafka_smoke.py` round-trip OK)

**재평가 — ADR-003 (5/23)**
1. rubric 재해석: 가점 대상은 *"event-driven 분석 갱신 구조"*, Kafka는 **예시일 뿐**
2. 규모 부정합: 30k row에 partition·consumer group·broker cluster·schema registry는 가치 없음
3. 클라우드 배포: managed Kafka(Confluent/Redpanda) → secret·SASL·무료 한도·추가 비용

**2차 결정 — Outbox 유지 + Kafka 제거 + LISTEN/NOTIFY + `SELECT FOR UPDATE SKIP LOCKED`**
- **SKIP LOCKED = Kafka consumer group 등가물**: N개 워커가 동일 NOTIFY를 받아도 row lock으로 정확히 1개만 처리 (Sidekiq `bulk_dequeue`, oban 등 프로덕션 큐의 표준 패턴)
- 변경 범위는 *메시지 채널뿐* (`aiokafka` → `asyncpg LISTEN/NOTIFY`). outbox·analytics·멱등성·catch-up·dead-letter는 그대로 보존

**장점** (ADR-003 Consequences)
- Kafka 운영 부담 0 / 클라우드 배포 단순(브로커·secret 제거) / 자산 보존 / 테스트 단순(testcontainers Postgres 단일 컨테이너)

**단점 & 완화** ← 점수 포인트 (장점만 나열하면 신뢰 하락; 단점+대응을 솔직히)
| 단점 | 완화 |
|------|------|
| NOTIFY는 휘발성 (유실 가능) | outbox에 남아 있어 catch-up 폴링(60s)이 처리 → 정합성 영향 0 |
| NOTIFY payload 8KB 한도 | `{event_id}` 메타만 전송, 본문은 worker가 SELECT로 fetch |
| scale 데모 설명 한 단계 추가 | 슬라이드에 "SKIP LOCKED = consumer group" 명시 |

**메타 교훈 (마무리 한 문장)**: 결정을 **번복하고 그 근거를 ADR로 남긴 것** 자체가 핵심 — right-sizing · YAGNI · *되돌릴 수 있는 결정(reversible decision)* 의 가치.

---

## 6. 배포 토폴로지 & 플랫폼 선택 이유 (2분) ★ 중점 ③ · 배포

**Two surfaces — 클라우드(외부 demo) + 로컬(분산 시연)** (Architecture §8)
| 환경 | 용도 | 컴포넌트 |
|------|------|---------|
| cloud (Vercel + Render) | 외부 reviewer 접속용 라이브 URL | Vercel(FE) + Render(API Web + outbox-publisher + analytics-worker) + Render Postgres |
| local (docker-compose) | `--scale analytics-worker=3` 분산 시연 | 위 동등 토폴로지 + 시드 데이터 |

- **왜 둘로 나눴나?** Render free tier에서 worker 다중 인스턴스는 비용·cold start 부담 → **scale 시연은 로컬**, **라이브 URL은 클라우드**. 동일 코드·토폴로지·마이그레이션, 분기는 환경변수뿐.

- **왜 Render + Vercel인가?**
  - 결정적 제약: LISTEN worker는 **항상 켜진 영속 연결**이 필요 → 순수 서버리스(Lambda / Cloud Run / Vercel Functions)는 **부적합**. web + worker + managed Postgres를 돌리는 *컨테이너 PaaS*가 필요.
  - Render: web·worker·Postgres를 **blueprint(`render.yaml`) 하나**로 선언. Vercel: 정적 FE 호스팅 최적 + CD 자동화.

- **왜 AWS가 아닌가?** (같은 right-sizing 논리)
  - 이 규모에 ECS Fargate + RDS + ALB + **NAT Gateway**는 비용 3~5배, VPC·IAM·IaC 운영 과중. 평가용 프로토타입엔 과함.
  - "수만 사용자·규제 준수·전담 인프라 인력"이 *실재할 때* 가치 → 확장 트리거 발생 시 평가 후 재평가 (Architecture §10).

- **운영 현실 메모 (배포도 의사결정이다)**: Render free Postgres는 **생성 30일 후 만료**. 라이브 데모를 유지하려면 DB를 유료($7/mo)로 전환해야 한다 → *무료 티어의 수명*도 배포 설계의 일부로 명시.

- **롤백**: 로컬 `docker-compose down -v && make up`; 클라우드 Render 1-click redeploy. 마이그레이션은 평가 종료까지 forward-only.

---

## 7. 확장성 & 병목 (1.5분 · 압축 가능)

- **수평 확장**: `docker-compose up --scale analytics-worker=3` — N개 워커가 동일 NOTIFY를 받아도 SKIP LOCKED로 1개만 처리. publisher는 단일이 기본이나 다중도 race-free.
- **단일 병목 (정직하게)**: Postgres 단일 인스턴스가 OLTP+OLAP+outbox+NOTIFY backplane 공존. NOTIFY는 인스턴스 글로벌 큐. → 평가 규모(수천 row)에선 무시 가능, 평가 후 read replica / 외부 broker (Architecture §5·§6).
- 발표 입증: 다이어그램 + scale=3 라이브 로그.

## 8. 보안 경계 (1분 · 압축 가능)

- **RBAC 3계층**: JWT 미들웨어(role + school_id 추출) → 라우터 역할 화이트리스트 → 서비스 row-level scope(`Class.teacher_id = current_user.id`)
- **데이터 보호**: bcrypt(cost≥12), refresh=HttpOnly+SameSite=Strict, 학생 PII 로그 masking, LLM엔 **토큰만(`학생A`) + k≥5** 익명성 (Architecture §7).

---

## 9. 시연 (10분)

자세한 순서는 `docs/notes/demo-rehearsal-checklist.md` 참조.

| # | 시연 | 강조 |
|---|------|------|
| 1 | 교사 로그인 → 대시보드 | 30명 학급의 평균/분포가 즉시 보임 |
| 2 | 성적 1건 입력 | Outbox commit (운영 변경과 같은 TX) |
| 3 | 분석 위젯 자동 갱신 | < 1초 (REQ-074) |
| 4 | `make demo-scale` | worker 3개 SKIP LOCKED 분산 처리 로그 |
| 5 | AI 비서에 "이 반 영어 평균은?" | 답변, 학생명은 토큰으로만 |
| 6 | 1명만 있는 반에서 같은 질문 | k<5 거부 메시지 |

## 10. 정량 결과 (1분)

- REQ-074 SLA(분석 반영 ≤60s) — `docs/notes/analytics-sla-baseline.md`
- 16개 회귀 테스트(analytics, chat, ratelimit) + 5개 E2E 시나리오
- 백엔드 176 passed / sanitizer 100% coverage

## 11. 다음 단계 (1분)

- 학부모 모바일 알림(FCM)
- 교과서/시험지 OCR → 자동 채점
- LLM 응답 캐시 + 비용 모니터링
- (인프라) 확장 트리거 도달 시 read replica / 외부 broker / 클라우드 재평가 — Architecture §10

---

## 부록 A. 예상 Q&A (ADR Risks가 곧 대본)

| 질문 | 답변 |
|------|------|
| 왜 Kafka를 안 썼나? | 도메인 규모. 30k row에 broker cluster·partition·schema registry는 의미 없음 |
| LISTEN/NOTIFY가 메시지 스트림인가? | Postgres 내장 pub/sub. Sidekiq·oban 등 프로덕션 큐가 SKIP LOCKED 기반으로 동작 |
| 알림이 유실되면? | outbox에 남아 catch-up 폴링(60s)이 처리 → 정합성 영향 0 |
| scale은 어떻게 보장하나? | N 워커가 같은 NOTIFY를 받아도 SKIP LOCKED로 정확히 1개만 처리 = consumer group 등가 |
| 왜 처음부터 LISTEN/NOTIFY를 안 했나? | 처음엔 rubric 문구상 Kafka가 가점에 안전해 보였다. 재해석 후 핵심이 'event-driven 구조'임을 확인, 규모를 보고 전환 (이 솔직함이 강점) |
| 왜 AWS가 아니라 Render인가? | 같은 right-sizing. 이 규모에 ECS+RDS+NAT GW는 비용·운영 과중. worker 영속 연결 때문에 순수 서버리스도 부적합 |
