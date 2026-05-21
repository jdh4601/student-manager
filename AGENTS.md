- MVP non‑negotiables: grade input/edit (0–100), instant total/avg, 9‑grade auto calc, radar chart; deliver S1–S2 scope first.
- Error contract: use AppException everywhere; JSON { detail, code } only (no plain HTTPException for business errors).
- Auth & isolation: JWT access 1h, refresh 7d (HttpOnly cookie); enforce role + school_id row scope on every query.
- Notifications: service stub early (Task 5) for side‑effects; router/preferences later (Task 23).
- TDD workflow: write failing tests → implement → verify; keep diffs small; no new deps without request.
- Auto-commit cadence: after each feature slice is implemented or its tests pass, perform an immediate auto commit with a small, focused diff and a concise, descriptive message (avoid batching unrelated changes).
- Plan hygiene: when a planned implementation step completes, immediately update the corresponding plan document (checkboxes/status in docs/superpowers/plans/*.md) before proceeding.
- Imports/exports: CSV in (students, grades), Excel/PDF out on client; avoid server file writes.
- Performance & security: API p95 ≤ 500ms; bcrypt; no PII in logs; no localStorage for tokens.
- Verification gates: pass backend tests (≥80% cov), S2 demo = login → grade input → radar chart → student view.

## Project

FastAPI + React/Vite 학생 성적·상담 관리 SaaS.

Primary docs:
- `docs/prd.md`
- `docs/design-spec.md`

## QA

```bash
npm run qa           # ruff + pytest + tsc
npm run e2e          # playwright
```

## Git Workflow

작업 단위 완료 시 → `git add` → `git commit` → `git push` 자동 수행.

## Jira Workflow

**Project**: SMS | **Board**: 2 | **Credentials**: `~/.claude/mcp.json → mcpServers.jira.env`
**Transitions**: `11`=해야할일 / `21`=진행중 / `31`=완료

1. 작업 배정 시 → 액티브 스프린트에 이슈 생성 후 `진행 중`(21) 전환
2. **이슈 하나의 작업이 끝날 때마다** → 즉시 해당 Jira 이슈를 `완료`(31)로 전환하고, 변경 내역을 코멘트로 남긴 뒤 (필요 시) 부모 에픽의 진척도와 남은 스프린트 이슈 목록을 출력. 다음 이슈 시작 전에 반드시 수행.
3. 스프린트 전체 완료 시 → `POST /rest/agile/1.0/sprint/{id}` `{"state":"closed"}`

## Known Remaining Work

- E2E 테스트 미작성: 상담·알림·import/export 플로우 (`frontend/e2e/`)
- Frontend `npm test` hang 이슈 (현재 `qa`에서 제외)
- SMTP 미연결: 초대·비밀번호 재설정이 `stub` 모드 (`AUTH_LINK_DELIVERY=stub`)
