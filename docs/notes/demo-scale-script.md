# 라이브 데모: analytics-worker 수평 확장

**연관**: SMS-67, REQ-075, Architecture §5.1
**소요**: 5분

발표 시 "Kafka consumer group이 동일 토픽을 N개 워커에 분산 처리한다"를 시연한다.

## 사전 조건

- Docker Desktop 또는 OrbStack 실행 중
- `kafka` 토픽 `KAFKA_NUM_PARTITIONS=3` (이미 `docker-compose.yml`에 설정됨)
- backend `analytics-worker`의 consumer group = `analytics-worker` (단일 그룹 → 파티션 분산)

## 단계

### 1. 기동

```bash
make demo-scale
```

내부적으로 `docker compose up -d --scale analytics-worker=3` 를 실행한다.
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

세 워커의 stdout이 prefix와 함께 한 스트림으로 흐른다. 각 워커가 자기에게 할당된
파티션의 메시지만 소비함을 확인한다 (Kafka의 group rebalance 로그가 처음 한 번
표시됨).

### 3. 부하 발생 (우측 터미널)

UI 또는 시드 스크립트로 grade/feedback/counseling을 다량 생성한다.

```bash
# 예: 시드 스크립트 활용 (SMS-71에서 demo_seed.py 추가 예정)
docker compose exec backend python seed.py --bulk-grades 100
```

또는 `frontend` 에서 평가 입력 화면을 통해 직접 추가.

### 4. 시연 포인트

- 좌측 로그 창에서 같은 `student_id`에 대한 이벤트가 어느 워커에서 처리됐는지
  prefix로 구분 가능
- `analytics.agg_*` 테이블이 1초 내 업데이트됨
- 한 워커 컨테이너를 내려보기:
  ```bash
  docker compose stop "sm-analytics-worker-2"
  ```
  Kafka rebalance 로그 뒤 나머지 두 워커가 해당 파티션을 인수받는 것이 보인다.

### 5. 정리

```bash
make demo-scale-down
```

## 문제 해결

| 증상 | 원인 / 처치 |
|------|------------|
| `Cannot create container ... name is already in use` | analytics-worker에 `container_name` 가 남아있는지 확인. SMS-67에서 제거됨. |
| 워커 1대에만 로그가 흐름 | 토픽 파티션이 1개일 수 있다. `kafka-topics --describe`로 partition count ≥ 3 확인. |
| Rebalance가 끝나지 않음 | `session.timeout.ms` 기본값(45s) 대기. 그래도 멈추면 `docker compose restart analytics-worker`. |
