# 발표 데모 리허설 체크리스트 (SMS-71)

목적: 시연 중 막힘/사고 발생 방지. 발표 1시간 전 1회 풀-리허설 + 직전 30분 dry-run.

## T-60분: 환경 정리

- [ ] `make demo-scale-down` → 기존 컨테이너 정리
- [ ] `docker system prune -f` → 디스크 여유 확보 (선택)
- [ ] 5432/9092/9093/18000/5173 포트 충돌 확인
  ```bash
  lsof -i :5432,9092,9093,18000,5173
  ```
- [ ] `git status` 깨끗한가 (커밋 안 된 실험 코드 없음)
- [ ] `.env` 또는 환경변수에 `KIMI_API_KEY` 설정 (실 LLM 시연 시) — 없으면 stub
- [ ] Wi-Fi 안정 (LLM API 호출 시 필요)

## T-30분: 시드 + 워밍업

- [ ] 기동
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.demo.yml \
      up -d --scale analytics-worker=3
  ```
- [ ] `docker compose ps` 로 모든 서비스 healthy 확인
- [ ] 데모 시드 (compose가 자동 실행하지 못한 경우 수동)
  ```bash
  docker compose exec backend python /scripts/demo_seed.py
  ```
  기대 출력: `TOTAL_NEW=1700` 내외 (이전에 시드됐다면 0 → idempotent)
- [ ] 브라우저에서 http://localhost:5173 접속 + 로그인 OK
  - 계정: `demo-teacher@example.com` / `password123`
- [ ] `/analytics` 대시보드에 6개 학기 데이터 노출 확인
- [ ] `/chat` 에서 "이 반 평균?" 질의 → 거부 메시지 아닌 응답 확인

## T-5분: 직전 확인

- [ ] 터미널 3개 준비:
  1. `make demo-scale-logs` — 분산 로그 (좌측)
  2. `psql -h localhost -U sm student_manager` — 즉석 SQL 확인용 (선택)
  3. `docker compose ps` — 시각화 백업
- [ ] 브라우저 탭 정리: 로그인 페이지 1개, 대시보드 1개, 챗봇 1개
- [ ] 화면 해상도 1280×800 이상 (사이드바·차트 visible)
- [ ] 시연용 임시 클래스/학생이 깨끗한지 — 필요 시 `frontend/e2e/chat-pii.spec.ts`
  의 cleanup 패턴 활용

## 시연 중 (10분)

1. **00:00** — `make demo-scale-logs` 열어두고 대시보드 진입. 6학기 평균 시각화.
2. **01:30** — `/students/{id}` 진입해 학생 상세 → 1과목 점수 +5 수정 → 저장
3. **02:00** — 대시보드로 돌아와 새로고침 → 평균이 갱신됐는지 확인 (≤ 1초)
4. **03:00** — `make demo-scale-logs` 화면을 잠깐 보여줘 worker 3개 분산 로그 강조
5. **04:00** — `/chat` 진입 → "이 반 영어 점수 분포 어때?" → 답변(stub or Kimi)
6. **05:30** — 임시 비어 있는 반(또는 4명만 있는 반)에서 같은 질문 → "5명 미만" 거부
7. **07:00** — analytics-worker 하나 stop (`docker compose stop sm-analytics-worker-2`) → rebalance 로그
8. **08:00** — 다시 stop된 worker start, 마무리 시각화

## 사고 대응

| 증상 | 1차 대응 |
|------|---------|
| 대시보드가 로드되지 않음 | 브라우저 새로고침 → `docker compose logs backend` → 401이면 재로그인 |
| 채팅 응답이 timeout | `KIMI_API_KEY` 미설정 가능성. stub fallback이 작동 중인지 라우터 코드 확인 |
| 분산 로그가 1대만 흐름 | `docker compose ps analytics-worker` 인스턴스 수 확인. 1이면 `--scale 3` 누락 |
| 시드 데이터가 안 보임 | `docker compose exec backend python /scripts/demo_seed.py` 수동 실행 |

## 사후 정리

- [ ] `make demo-scale-down`
- [ ] `docker volume rm student-manager_pgdata student-manager_kafkadata` (선택)
- [ ] `docs/notes/demo-rehearsal-result-YYYY-MM-DD.md` 생성해 실측 결과 기록

## 리허설 결과 로그

| 날짜 | 시도 | 시간(s) | 막힘 포인트 | 비고 |
|------|------|--------|-----------|------|
| 2026-05-22 | 1차 | _TBD_ | _TBD_ | 첫 dry-run 후 갱신 예정 |
