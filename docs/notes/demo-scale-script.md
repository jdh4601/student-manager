# 라이브 데모: analytics-worker 수평 확장

**연관**: SMS-67, REQ-075, Architecture §5.1, ADR-003
**소요**: 5분

발표 시 "Postgres LISTEN/NOTIFY + `SELECT FOR UPDATE SKIP LOCKED`가 동일 outbox 이벤트를 N개 워커에 race-free로 분산 처리한다"를 시연한다 (Kafka consumer group의 partition 분배 등가).

## 사전 조건

- Docker Desktop 또는 OrbStack 실행 중
- backend `analytics-worker`가 4개 채널(`grade_events`/`attendance_events`/`feedback_events`/`counseling_events`)을 LISTEN
- 외부 message broker 없음 — Postgres가 backplane 겸용

## 단계

### 1. 기동

```bash
make demo-scale
```

내부적으로 `docker compose up -d --scale analytics-worker=3`을 실행한다.
docker가 `sm-analytics-worker-1`, `-2`, `-3` 세 컨테이너를 띄운다.

확인:

```bash
docker compose ps analytics-worker
```

세 라인이 보여야 한다 (각각 다른 컨테이너 ID).

### 2. 분산 로그 보기 (좌측 터미널)

```bash
make demo-scale-logs
```

세 워커의 stdout이 prefix와 함께 한 스트림으로 흐른다. 동일 NOTIFY가 3 워커 모두에게 도착하지만, 각 outbox row는 `FOR UPDATE SKIP LOCKED` 경쟁에서 정확히 1개 워커만 잠그고 처리하는 것을 확인한다.

### 3. 부하 발생 (우측 터미널)

UI 또는 시드 스크립트로 grade/feedback/counseling을 다량 생성한다.

```bash
docker compose exec backend python /scripts/demo_seed.py
```

또는 `frontend`에서 평가 입력 화면을 통해 직접 추가.

### 4. 시연 포인트

- 좌측 로그 창에서 같은 `event_id`에 대한 처리 로그가 **정확히 한 워커**에서만 출력됨 (SKIP LOCKED 검증)
- `analytics.agg_*` 테이블이 1초 내 업데이트
- `SELECT count(*) FROM public.outbox WHERE processed_at IS NULL`이 즉시 0에 수렴
- 한 워커 컨테이너를 내려보기:
  ```bash
  docker compose stop "sm-analytics-worker-2"
  ```
  남은 두 워커가 자연스럽게 잔여 부하를 흡수 (NOTIFY는 그대로 fanout, SKIP LOCKED가 분배). rebalance 대기 시간 없음.

### 5. 정리

```bash
make demo-scale-down
```

## 문제 해결

| 증상 | 원인 / 처치 |
|------|------------|
| `Cannot create container ... name is already in use` | analytics-worker에 `container_name`이 남아있는지 확인. SMS-67에서 제거됨. |
| 워커 1대에만 로그가 흐름 | 부하가 적어 row 경쟁 윈도우가 너무 짧음. `demo_seed.py`로 더 많은 row를 한 번에 stage하면 분산이 가시화됨. |
| NOTIFY가 도착하지 않음 | `python scripts/listen_notify_smoke.py`로 round-trip 검증. Postgres connection이 끊겼다면 worker 재시작. |
| processed_at이 NULL로 남음 | catch-up 폴링(60s)이 다음 tick에 자동 회수. 즉시 보고 싶다면 `LISTEN_NOTIFY_CATCHUP_INTERVAL=5` 환경변수로 재기동. |
