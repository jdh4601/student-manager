# ADR-002: CDC 패턴 — Outbox + Kafka KRaft

**상태**: Accepted
**작성일**: 2026-05-03
**작성자**: DongHyun Jung
**선행 결정**: ADR-001 (OLAP 분석 파이프라인 + 인프라 방향)
**선행 노트**: `history/2026-05-03-v2.1-architecture-grill.md` (Q4)

---

## Context

ADR-001에서 운영(`public`) → 분석(`analytics`) 적재를 **메시지 스트림 기반**으로 결정했다. 평가 rubric은 *"Apache Kafka와 같은 메시지 스트림"*을 명시 가점 항목으로 둔다.

남은 결정은 **운영 트랜잭션의 변경을 어떻게 Kafka 토픽으로 전달할 것인가** — 즉 CDC(Change Data Capture) 패턴 선택이다.

### 자원·시간 제약

- 1인 + Claude Code
- Kafka·Redpanda·Debezium 미경험
- 평가까지 2개월, critical path는 W2~W5 (5주)
- 발표 Q&A에서 "broker 다운 시 어떻게 됩니까?", "이벤트 유실은?" 질문 방어 필요

---

## Decision

**Outbox 패턴 + Kafka KRaft 단일 노드 + app publisher (aiokafka)**

### 구체화

1. **Outbox 테이블** (`public.outbox`)
   - 운영 트랜잭션 안에서 도메인 변경(grade UPSERT 등) 직후 outbox row를 같은 트랜잭션으로 INSERT
   - 컬럼: `event_id BIGSERIAL`, `aggregate_type`, `aggregate_id`, `payload JSONB`, `created_at`, `sent_at TIMESTAMP NULL`

2. **Publisher 프로세스** (`app/workers/outbox_publisher.py`)
   - `WHERE sent_at IS NULL ORDER BY event_id` polling (또는 LISTEN으로 deal-trigger)
   - aiokafka producer로 `grade_events` 등 토픽에 발행
   - 발행 성공 시 `sent_at = now()` UPDATE

3. **Consumer** = `analytics-worker` (`app/workers/analytics.py`)
   - aiokafka consumer, consumer group + offset commit
   - idempotent UPSERT (`ON CONFLICT DO UPDATE`)로 중복 이벤트 무해화

4. **Broker**: Kafka KRaft 단일 노드 (docker-compose)
   - **Fallback**: W3 금요일 PoC fail 시 Redpanda 단일 노드로 교체
     - Kafka API 호환 → publisher/consumer 코드 변경 0
     - docker-compose 이미지 한 줄 교체

---

## Alternatives Considered

| 대안 | 메시지 스트림 가점 | 유실 방어 | 학습 곡선 | 1인·2개월 적합도 | 결과 |
|------|----|----|----|----|----|
| **A. Debezium + Kafka Connect** | ✅ Kafka 명시 | ✅ WAL 직접 읽음 → 강력 | 🔴 높음 (Connect, Schema Registry, 운영 디버깅) | 🔴 critical path 위험 | ❌ |
| **B. Outbox + app publisher (aiokafka) + Kafka** ★ | ✅ Kafka 명시 | ✅ outbox commit → 부팅 catch-up | 🟡 중간 (Kafka 자체) | 🟢 application 코드로 처리 | **✅ 채택** |
| **C. App-direct Kafka publish** | ✅ Kafka 명시 | 🔴 broker 다운 시 publish 실패 → 이벤트 유실 | 🟢 낮음 | 🟢 빠름 | ❌ Q&A 방어 약함 |
| D. PG LISTEN/NOTIFY (Kafka 없음) | 🔴 평가자 해석 의존 | 🟡 NOTIFY는 휘발성 | 🟢 낮음 | 🟢 빠름 | ❌ (ADR-001에서 폐기) |

### 거부 사유 상세

**A. Debezium**: 가장 정석적이지만, Connect cluster + Schema Registry 등 추가 컴포넌트가 늘어나며, 1인 미경험자가 W3에 PoC를 끝낼 가능성이 낮다. 디버깅 시 인프라 레이어가 두꺼워 발표 데모 직전 대형 장애 위험.

**C. App-direct**: 가장 단순하지만 broker 다운 시 트랜잭션은 commit되었는데 이벤트는 유실되는 실패 모드가 있다. 발표 Q&A에서 "어떻게 신뢰성을 보장합니까?" 질문에 답변이 약하다.

**D. LISTEN/NOTIFY**: 외부 메시지 브로커가 아니므로 가점 인정 여부가 평가자 해석에 달린다. ADR-001에서 이미 폐기됨.

---

## Consequences

### 긍정적

- **메시지 스트림 가점 명시 충족** (Kafka)
- **이벤트 유실 방지**: outbox row가 commit되면 publisher가 다운돼도 부팅 시 `WHERE sent_at IS NULL` 쿼리로 catch-up 가능 → 발표 Q&A 방어 강력
- **Application 코드만으로 구현**: 별도 Connect cluster 불필요 → 1인이 디버깅 가능한 범위
- **테스트 용이**: testcontainers Kafka로 통합 테스트 가능

### 부정적

- 운영 트랜잭션에 outbox INSERT 추가 → write latency 약간 증가
  - **측정 계획**: W3에 grade UPSERT p95 latency before/after 비교 (목표: +5ms 이하)
- Publisher 프로세스 신설 → 모니터링 대상 증가
- Kafka KRaft 운영 학습 부담 (W3 PoC가 critical)

### 중립적

- Outbox 테이블이 운영 DB에 추가되나 평가용 데이터 규모에서 부담 없음
- 향후 Debezium으로 전환 시에도 outbox 테이블은 그대로 사용 가능 (Debezium이 outbox를 source로 읽음)

---

## Risks & Mitigation

| ID | 리스크 | 대응 |
|----|--------|------|
| R-1 | Kafka KRaft docker-compose 설정 막힘 (W3) | ✅ **closed (2026-05-04)** — `confluentinc/cp-kafka:7.6.1` KRaft 모드로 health check ≤30s 통과, `scripts/kafka_smoke.py` round-trip OK. Redpanda fallback 불필요. |
| R-2 | testcontainers Kafka 부팅 느려 CI 시간 폭증 | session-scoped fixture, 일부 테스트는 docker-compose 의존으로 분리 |
| R-3 | Outbox row가 누적되어 테이블 비대화 | 평가용 환경에서는 무시 가능. 운영 환경에선 `sent_at < now() - 7d` 주기 archival (평가 후) |
| R-4 | Publisher와 운영 라우터 둘 다 같은 outbox row를 처리 (race) | publisher만 `sent_at` 업데이트. 라우터는 INSERT만 수행 → race 없음 |
| R-5 | 발표 시 평가자가 Outbox 패턴 정의 혼동 | 발표 슬라이드 1장에 "트랜잭션 안에 outbox INSERT → publisher가 토픽 발행" 다이어그램 명시 |

---

## Implementation Notes

### Outbox 테이블 DDL (예시)

```sql
CREATE TABLE public.outbox (
  event_id        BIGSERIAL PRIMARY KEY,
  aggregate_type  VARCHAR(50) NOT NULL,   -- 'grade' | 'attendance' | 'feedback' | 'counseling'
  aggregate_id    UUID NOT NULL,
  topic           VARCHAR(50) NOT NULL,   -- 'grade_events' 등
  payload         JSONB NOT NULL,
  created_at      TIMESTAMP NOT NULL DEFAULT now(),
  sent_at         TIMESTAMP NULL
);
CREATE INDEX outbox_unsent_idx ON public.outbox (event_id) WHERE sent_at IS NULL;
```

### 라우터에서 outbox INSERT 위치

`app/services/grades.py`의 grade UPSERT 직후, **같은 트랜잭션** 안에서 outbox INSERT:

```python
async with db.begin():
    grade = await upsert_grade(db, ...)
    await db.execute(insert(Outbox).values(
        aggregate_type="grade",
        aggregate_id=grade.id,
        topic="grade_events",
        payload={"grade_id": str(grade.id), "student_id": ..., "op": "UPSERT"},
    ))
# commit 완료 시점에 outbox row와 grade가 같이 영속화됨
```

### Publisher pseudo-code

```python
# app/workers/outbox_publisher.py
async def main() -> None:
    producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP)
    await producer.start()
    while True:
        rows = await fetch_unsent(limit=100)  # WHERE sent_at IS NULL ORDER BY event_id
        for row in rows:
            await producer.send_and_wait(row.topic, row.payload)
            await mark_sent(row.event_id)
        if not rows:
            await asyncio.sleep(0.5)
```

### Consumer (analytics-worker) pseudo-code

```python
# app/workers/analytics.py
async def main() -> None:
    consumer = AIOKafkaConsumer(
        "grade_events", "attendance_events", ...,
        bootstrap_servers=BOOTSTRAP,
        group_id="analytics-worker",
        enable_auto_commit=False,
    )
    await consumer.start()
    async for msg in consumer:
        await refresh_aggregate(msg.value)  # idempotent UPSERT
        await consumer.commit()
```

---

## Validation Criteria (W3~W4)

- [ ] Outbox INSERT 추가 후 grade UPSERT p95 latency 증가 ≤ 5ms (testcontainers 환경)
- [ ] Publisher 강제 종료 → 재기동 후 unsent rows 모두 발행
- [ ] Consumer 강제 종료 → 재기동 후 offset에서 재구독 (이벤트 누락 0)
- [ ] `--scale analytics-worker=3`에서 동일 메시지 중복 처리 시에도 `analytics.agg_*` 결과 동일 (idempotency)

---

## References

- ADR-001 §Decision 2 (메시지 스트림 도입)
- `history/2026-05-03-v2.1-architecture-grill.md` Q4 (CDC 패턴 결정 트리)
- Architecture v1.1 §4.1 (운영 흐름 — Outbox + Kafka)
- Design Spec v2.1 §9 (Analytics Layer — Outbox DDL + publisher/consumer)
