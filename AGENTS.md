oh-my-codex — Student Manager Quick Directive

Source: docs/superpowers/plans/2026-03-20-student-manager-full-implementation.md, docs/prd.md (v2.0)

- MVP non‑negotiables: grade input/edit (0–100), instant total/avg, 9‑grade auto calc, radar chart; deliver S1–S2 scope first.
- Error contract: use AppException everywhere; JSON { detail, code } only (no plain HTTPException for business errors).
- Auth & isolation: JWT access 1h, refresh 7d (HttpOnly cookie); enforce role + school_id row scope on every query.
- Notifications: service stub early (Task 5) for side‑effects; router/preferences later (Task 23).
- TDD workflow: write failing tests → implement → verify; keep diffs small; no new deps without request.
- Imports/exports: CSV in (students, grades), Excel/PDF out on client; avoid server file writes.
- Performance & security: API p95 ≤ 500ms; bcrypt; no PII in logs; no localStorage for tokens.
- Verification gates: pass backend tests (≥80% cov), S2 demo = login → grade input → radar chart → student view.
