# Student Manager

FastAPI + React/Vite 학생 성적·상담 관리 SaaS. 문서: `docs/prd.md`, `docs/design-spec.md`

## Coding Rules

- Error contract: `AppException` only → `{ detail, code }` JSON (no plain HTTPException for business errors)
- Auth: JWT access 1h / refresh 7d (HttpOnly cookie); enforce `role + school_id` scope on every query
- TDD: failing test → implement → verify; keep diffs small; no new deps without request
- Imports/exports: CSV in (students, grades), Excel/PDF out on client; no server file writes
- Security: API p95 ≤ 500ms; bcrypt; no PII in logs; no localStorage for tokens

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

## Jira/Linear Workflow
- TDD: 실패하는 테스트를 먼저 작성한 뒤 구현
- 이슈 완료 시: 테스트 → conventional commit → Jira/Linear 상태 전환 → codemap 업데이트
- 한국어 로컬라이즈된 Jira 프로젝트는 한국어 이슈 타입('에픽', '작업', '스토리') 사용
- REST API 호출보다 MCP 도구(mcp__jira__*, Linear MCP) 우선 사용

## 남은 작업

- Frontend `npm test` hang: 근본원인 규명 완료 (Node 25≠vitest 1.6 + node_modules가 Linux 바이너리). fix는 Node 20 클린 재설치 필요. `test:run` 스크립트 추가됨 (watch 모드 분리)
- SMTP 미연결: 초대·비밀번호 재설정이 `stub` 모드 (`AUTH_LINK_DELIVERY=stub`)
- 교사 OAuth 실 모드: Google Cloud OAuth 클라이언트 등록 + `GOOGLE_CLIENT_ID/SECRET`·`ALLOWED_TEACHER_DOMAINS`·`OAUTH_DEFAULT_SCHOOL_ID` 설정 필요 (현재 stub은 비-production만 허용)

> E2E 테스트는 작성 완료 (`frontend/e2e/` 11 spec). 백엔드 200 passed / 커버리지 81%.
