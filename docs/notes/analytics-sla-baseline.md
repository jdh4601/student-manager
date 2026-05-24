# Analytics 반영 SLA Baseline (REQ-074)

**연관**: SMS-68
**기준**: 운영 commit → analytics 위젯 반영 ≤ 60초

## 측정 방법

`frontend/e2e/analytics-sla.spec.ts` (Playwright)

```bash
make demo-scale          # Kafka + analytics-worker 기동
cd frontend
E2E_KAFKA=1 \
E2E_ANALYTICS_ITERATIONS=5 \
PW_REUSE=1 \
npx playwright test analytics-sla.spec.ts --reporter=line
```

`PW_REUSE=1`은 이미 띄워둔 backend/frontend를 재사용한다. 호스트가 다르면
`E2E_API_BASE=http://...:18000/api/v1/` 로 덮어쓰면 된다.

## Baseline (2026-05-21, 로컬 — n=3)

> 실제 로컬 measurement 전 placeholder. 첫 측정 시 이 표를 갱신할 것.

| 항목        | 값      |
| ----------- | ------- |
| sample size | 3       |
| median      | _TBD_   |
| p95         | _TBD_   |
| target      | 60_000  |
| 환경        | Docker Desktop, M-series Mac, single broker, partitions=3 |

## 영향 인자

- Kafka batch / linger.ms (현재 기본값)
- outbox poll 주기 (`outbox_publisher`)
- analytics-worker consumer poll interval
- DB write 부하 — partition별 1워커가 처리

## 회귀 조건

이 측정값이 30s 이상 늘어나면:
1. `outbox_publisher` lag 확인 (`outbox.published_at IS NULL` 비율)
2. `analytics-worker` 처리 시간 — `make demo-scale-logs`
3. Kafka consumer group lag — `kafka-consumer-groups --describe`
