# 발표용 — 테스트 피라미드 (②)

**목적**: 교수 커리큘럼의 "유닛 → 통합 → E2E" 축 충족 + 실측 커버리지 제시.
**핵심 메시지**: "테스트 통과 한 줄"이 아니라, **3계층이 각기 다른 것을 검증**하고, 백엔드 **81% 커버리지**로 뒷받침된다.

> ⚠️ 중간발표/PRD의 "E2E 미작성"은 **stale** — 실제로는 3계층이 모두 존재한다. 발표에서 이를 정정한다.

---

## 1. 피라미드 (실측, 2026-05-31)

```
                   ╱╲
                  ╱E2E╲          Playwright 11 spec — 사용자 플로우 (실 브라우저)
                 ╱──────╲        landing·login·grades·feedback·analytics-rbac·chat-pii·
                ╱  통합   ╲       student-parent-mobile·class-delete·prd-user-stories
               ╱──────────╲
              ╱            ╲     통합 testcontainers(실 Postgres) — outbox→analytics 정합성
             ╱   단위(unit)  ╲    grade_pipeline_e2e·idempotency_e2e·analytics_query_batch·
            ╱────────────────╲   chat_context_join·demo_seed_outbox
           ╱                  ╲
          ╱  backend 200 passed ╲  단위 — 계산·권한·검증 (서비스/스키마/유틸)
         ╱──────────────────────╲
```

| 계층 | 위치 | 수량 | 검증 대상 |
|------|------|------|-----------|
| **단위 (unit)** | `backend/tests/test_*.py` | **200 passed** (10 skip) | 9등급 계산, RBAC 스코프, school_id 격리, LLM sanitizer, OAuth 도메인 게이트 |
| **통합 (integration)** | `backend/tests/integration/` | testcontainers 실 Postgres | outbox→publisher→worker→`analytics.*` row 정합성, SKIP LOCKED scale=3 중복 없음, idempotency |
| **E2E** | `frontend/e2e/*.spec.ts` | **11 spec** | 로그인→성적 입력, 분석 SLA(≤1분), RBAC 차단, 챗봇 PII 마스킹, 모바일 반응형 |

**백엔드 커버리지: 81%** (`pytest --cov`, 3350 stmt / 631 miss). 핵심 도메인은 더 높음:
grade 97% · feedback 96% · auth 96% · oauth 77% · llm_sanitizer 100% · grade_calculator 100%.

---

## 2. 발표 서사 (말할 내용)

1. **유닛**은 빠르고 격리 — 성적 등급 계산·권한 검증 같은 순수 로직. (실 DB 없이 ms 단위)
2. **통합**은 testcontainers로 **진짜 Postgres**를 띄워 outbox CDC 파이프라인의 정합성을 검증. "scale=3에서도 이벤트 중복 처리 0"을 자동 검증 — 우리 아키텍처의 핵심 주장을 테스트가 보증.
3. **E2E**는 Playwright로 **실 브라우저**에서 사용자 플로우 전체를 검증. 분석 반영 ≤1분 SLA, RBAC 차단, 챗봇 PII 마스킹까지.
4. 세 계층이 **서로 다른 실패를 잡는다** — 유닛은 로직 버그, 통합은 컴포넌트 간 계약, E2E는 사용자 경험.

---

## 3. 정직성 — frontend 단위 테스트 환경 이슈 (해결책 명시)

frontend 컴포넌트 단위 테스트 10개(`src/__tests__/`)는 작성돼 있으나, **호스트 환경 문제로 현재 hang**한다. 근본 원인을 규명했다 (`docs/notes/frontend-test-env-fix.md`):

- `node_modules`가 **Linux 바이너리**로 설치돼 macOS darwin 바이너리 누락
- 시스템 **Node 25 ≠ vitest 1.6** (Node 20 필요)

→ E2E(Playwright 11)가 frontend 동작을 **실 브라우저로 더 강하게 검증**하므로, 평가 시연의 frontend 신뢰성은 E2E로 충분히 확보된다. 컴포넌트 단위 테스트는 Node 20 클린 설치 후 복구 (문서의 fix 명령 참조).

> 발표 시 이 슬라이드는 **약점을 숨기지 않고 "원인 규명+해결책 보유"로 프레이밍** — 디버깅 역량의 증거.

---

## 4. 데모 (라이브)

- **백엔드 통합/단위**: `cd backend && pytest -q` → 200 passed (또는 `pytest -m integration`)
- **E2E 1개 라이브**: `cd frontend && npx playwright test e2e/landing-login-grade.spec.ts` (짧고 시각적)
- **커버리지**: `pytest --cov=app --cov-report=term` → 81% 한 컷

---

## 5. 발표 전 할 일

- [ ] 피라미드 다이어그램을 슬라이드로 시각화 (위 §1)
- [ ] E2E 1개 라이브 실행 리허설 (RISK-010 데모 환경 점검)
- [ ] (선택) frontend 단위 테스트 Node 20 클린 설치로 복구 → "3계층 + frontend unit" 완성
