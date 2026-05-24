# Analytics 반영 SLA Baseline (REQ-074)

**연관**: SMS-68, ADR-003
**기준**: 운영 commit → analytics 위젯 반영 ≤ 60초

## 측정 방법

`frontend/e2e/analytics-sla.spec.ts` (Playwright)

```bash
make demo-scale          # Postgres + outbox-publisher + analytics-worker 기동
cd frontend
E2E_ANALYTICS_ITERATIONS=5 \
PW_REUSE=1 \
npx playwright test analytics-sla.spec.ts --reporter=line
```

`PW_REUSE=1`은 이미 띄워둔 backend/frontend를 재사용한다. 호스트가 다르면
`E2E_API_BASE=http://...:18000/api/v1/`로 덮어쓰면 된다.

## Baseline (2026-05-21, 로컬 — n=3)

> ⚠ Kafka 기반 측정값이었음. ADR-003 LISTEN/NOTIFY 전환 후 재측정 필요 — TBD.

| 항목        | 값      |
| ----------- | ------- |
| sample size | 3       |
| median      | _TBD (Kafka 기준 측정값 무효화)_  |
| p95         | _TBD_   |
| target      | 60_000  |
| 환경        | Docker Desktop, M-series Mac, Postgres single instance |

## 영향 인자

- `LISTEN_NOTIFY_IDLE_POLL_INTERVAL` (publisher 빈-poll 대기, 기본 0.5s)
- outbox row 적재량 (publisher batch 크기 100 고정)
- analytics-worker `LISTEN_NOTIFY_CATCHUP_INTERVAL` (NOTIFY 유실 보완 폴링 주기, 기본 60s)
- DB write 부하 — SKIP LOCKED 경쟁에서 잠근 worker 1개가 처리
- `OUTBOX_MAX_RETRIES` (기본 3, transient 오류 재시도 횟수)

## 회귀 조건

이 측정값이 30s 이상 늘어나면:
1. publisher lag 확인: `SELECT count(*) FROM public.outbox WHERE sent_at IS NULL`
2. worker lag 확인: `SELECT count(*) FROM public.outbox WHERE sent_at IS NOT NULL AND processed_at IS NULL`
3. dead-letter 누적: `SELECT count(*), max(occurred_at) FROM analytics.dead_letter_event`
4. `make demo-scale-logs`로 워커 처리 시간 관찰
