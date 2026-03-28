# Student Manager Full Implementation Plan

**Goal:** Build a full-stack student grade & counseling management SaaS (FastAPI + React 18) following the Design Spec v2.0

**Architecture:** FastAPI backend with SQLAlchemy 2.0 ORM, PostgreSQL (Supabase), JWT auth. React 18 frontend with TypeScript, Tailwind CSS, Zustand, TanStack Query, Recharts. Multi-tenant isolation via `school_id` row-level filtering. Client-side file generation (SheetJS, jsPDF).

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, pytest / React 18, TypeScript, Vite, Tailwind CSS, Zustand, TanStack Query, Recharts

**Spec:** `docs/design-spec.md` (v2.0 확정)
**PRD:** `docs/prd.md` (v2.0 확정)

---

## Implementation Status — 2026-03-26

- [x] Backend: project scaffold, config, DB base, health route
- [x] Backend: all 14 models + seed (Alembic initial migration placeholder; real migration pending)
- [x] Backend: utils (bcrypt/JWT, 9-grade calc) + tests
- [x] Backend: auth dependencies, auth service + router (login/refresh/logout/me)
- [x] Backend: semesters, classes, subjects CRUD
- [x] Backend: users (student/parent create, list, deactivate)
- [x] Backend: grades CRUD + summary (bulk pending); security scoped to teacher-owned students
- [x] Backend: students detail/update, attendance, special notes
- [x] Backend: feedbacks CRUD (owner/visibility rules)
- [x] Backend: counselings CRUD + sharing + filters
- [x] Backend: notifications (list/mark-read/read-all, preferences) + side-effects
- [x] Backend: CSV imports (students, grades)
- [x] Security: rate limit on `/auth/login` (5/min), JSON 429 handler
- [ ] Security: additional cross-school isolation tests (nice-to-have)
- [x] Frontend: Vite+React+TS+Tailwind scaffold, axios client with refresh interceptor
- [x] Frontend: Zustand auth store, `ProtectedRoute`, layout (`Sidebar`, `Header`)
- [x] Frontend: `LoginPage`
- [x] Frontend: API modules/hooks — Semesters, Classes/Subjects, Users/Students, Grades, Notifications, Feedback, Counseling
- [x] Frontend: pages — Student List, Student Detail, Grades (autosave grid), Notifications
- [x] Frontend: pages — Dashboard, Feedback, Counseling, Grades radar chart
- [x] Frontend: export (Excel/PDF), responsive polish
- [x] Tests: backend unit tests passing locally (27/27 on Python 3.12)
- [ ] QA: integration test suite and coverage target ≥ 80%
- [x] Infra: backend Dockerfile + docker-compose (db/backend/frontend) for local run
- [x] Docs: README Quick Start updated (Compose, Docker backend + local FE)
- [x] Docs: PRD delta section added (MVP vs. PRD differences)
- [x] Build: Vite plugin-less config to allow TSX build without devDeps

**Notes**
- Runtime: recommend Python 3.11/3.12. `bcrypt` pinned (4.2.0) for `passlib` compatibility.
- Security: ownership checks enforced across services; cross-school isolation tests to be added.
- Local run: `docker compose up --build` brings up Postgres, backend (FastAPI), and frontend (Vite dev) with proxy.
- Frontend build: `@vitejs/plugin-react` omitted to support restricted envs; re-enable in dev when available for HMR.
- API shapes (MVP): list endpoints return arrays (no pagination); `GET /notifications` returns list only; `read-all` → `{ updated }`.
- Auth errors: business errors use `{ detail, code }`, some 401/403 from auth guard may use FastAPI default format.
- Semesters list: teacher-only in MVP (student/parent expansion planned).

---

## 2026-03-26 Update

- Frontend layout: responsive sidebar (mobile overlay + header toggle), dashboard polished with stats and quick links.
- Radar chart: fixed 0–100 scale via `PolarRadiusAxis`; added chart tab on Grades page.
- Export: added `utils/exportHelpers.ts` with Excel/PDF exports; wired buttons on Grades and Student List pages.
- Performance: code-split `xlsx` and `jspdf` via dynamic import to reduce initial bundle size.
- Feedback/Counseling: completed pages with create/update/delete flows using query hooks.
- Infra: added backend `Dockerfile` and `docker-compose.yml` (Postgres + backend + frontend dev); README Quick Start updated.
- Build: simplified Vite config (no plugin) to allow TSX build in restricted environments.

---

## Remaining Tasks

- QA: add integration tests and raise coverage to ≥ 80%; basic FE integration/e2e checks.
- Security tests: add cross-school isolation tests across services (nice-to-have, backend).
- Dev UX: re-enable `@vitejs/plugin-react` locally for React Refresh when devDeps are available.
- Data migrations: auto-generate first Alembic migration on startup if empty (docker-compose). Replace with fixed migration & CI check for prod.
- Grades: implement `POST /grades/bulk` (or keep CSV import only and update docs).
- API consistency: add pagination `{ total, items }` across list endpoints; consider `unread_count` in notifications or keep client-computed.
- Error contract: unify 401/403 to `{ detail, code }` (wrap auth guard) or document exception; ensure consistency.
- Roles/Scopes: expand `GET /semesters` (and necessary reads) to student/parent; add minimal student/parent read-only views in FE.
- UX polish: replace raw UUID inputs in Feedback/Counseling forms with student selector; add validation and toasts.
- Accessibility: audit focus states, landmarks, and semantic labels; finalize responsive tweaks.

---

## File Structure

### Backend

```
backend/
├── app/
│   ├── main.py                        # FastAPI app, CORS, router includes
│   ├── config.py                      # Settings via pydantic-settings
│   ├── database.py                    # async engine, sessionmaker, Base
│   ├── dependencies/
│   │   ├── auth.py                    # get_current_user, require_role, require_teacher_of_student
│   │   └── db.py                      # get_db async generator
│   ├── models/
│   │   ├── school.py, user.py, class_.py, student.py, parent_student.py
│   │   ├── subject.py, semester.py, grade.py, attendance.py, special_note.py
│   │   ├── feedback.py, counseling.py, notification.py, notification_preference.py
│   ├── schemas/
│   │   ├── auth.py, user.py, class_.py, semester.py, subject.py, grade.py
│   │   ├── student.py, attendance.py, special_note.py, feedback.py
│   │   ├── counseling.py, notification.py, common.py
│   ├── routers/
│   │   ├── auth.py, users.py, semesters.py, classes.py, grades.py
│   │   ├── students.py, feedbacks.py, counselings.py, notifications.py, imports.py
│   ├── services/
│   │   ├── auth.py, user.py, grade.py, student.py, feedback.py
│   │   ├── counseling.py, notification.py, import_.py
│   └── utils/
│       ├── grade_calculator.py        # calculate_grade(score) -> rank
│       └── security.py                # hash_password, verify_password, create_jwt, decode_jwt
├── alembic/
│   └── versions/                      # migration files
├── seed.py                            # Alembic seed script (School + Teacher)
├── requirements.txt
├── pyproject.toml
└── tests/
    ├── conftest.py                    # test DB, client fixture, auth helpers
    ├── test_auth.py, test_users.py, test_semesters.py, test_classes.py
    ├── test_grades.py, test_students.py, test_feedbacks.py
    ├── test_counselings.py, test_notifications.py, test_imports.py
```

### Frontend

```
frontend/
├── src/
│   ├── App.tsx                        # Router, QueryClient, global providers
│   ├── api/
│   │   ├── client.ts                  # axios instance, interceptors (refresh token)
│   │   ├── auth.ts, semesters.ts, classes.ts, subjects.ts, users.ts
│   │   ├── grades.ts, students.ts, feedbacks.ts, counselings.ts, notifications.ts
│   ├── components/
│   │   ├── ui/                        # Button, Input, Select, Modal, Toast, Badge
│   │   ├── layout/                    # AppLayout, Sidebar, Header
│   │   ├── auth/                      # LoginForm, ProtectedRoute
│   │   ├── grades/                    # GradeTable, GradeSummary, RadarChart
│   │   ├── students/                  # StudentList, StudentDetail, AttendanceForm, SpecialNoteForm
│   │   ├── feedbacks/                 # FeedbackForm, FeedbackList
│   │   ├── counselings/               # CounselingForm, CounselingList
│   │   └── notifications/             # NotificationBell, NotificationList
│   ├── hooks/
│   │   ├── useAuth.ts, useGrades.ts, useStudents.ts
│   │   ├── useFeedbacks.ts, useCounselings.ts, useNotifications.ts
│   ├── stores/
│   │   ├── authStore.ts               # access_token, user info, role
│   │   └── notificationStore.ts       # unread_count
│   ├── pages/
│   │   ├── LoginPage.tsx, DashboardPage.tsx, SetupPage.tsx
│   │   ├── StudentListPage.tsx, StudentDetailPage.tsx, GradesPage.tsx
│   │   ├── FeedbackPage.tsx, CounselingPage.tsx, NotificationsPage.tsx
│   ├── utils/
│   │   ├── gradeCalculator.ts
│   │   └── exportHelpers.ts           # Excel/PDF export helpers
│   └── types/
│       └── index.ts                   # shared TypeScript interfaces
├── package.json, tsconfig.json, tailwind.config.ts, vite.config.ts
└── index.html
```

---

## Summary: Sprint → Task Mapping

| Sprint | Tasks | PRD Requirements |
|--------|-------|-----------------|
| S0 (Week 1-2) | Task 1-6 | Project setup, DB models, auth infra, notification stub |
| S1 (Week 3-4) | Task 7-15 | REQ-001~004, 010, 011, 012(proto) |
| S2 (Week 5-6) | Task 16-19 | REQ-012(완성), 015, 020~022 |
| S3 (Week 7-8) | Task 20-21 | REQ-030~032 |
| S4 (Week 9-10) | Task 22-24 | REQ-033, 040~042, 050, 051 |
| S5 (Week 11-12) | Task 25-29 | REQ-014, 023, 060, QA |

**Total: 29 tasks, ~150 steps**

### Reviewer Issues Addressed

| Issue | Fix |
|-------|-----|
| Error response format (`{ detail, code }`) | `AppException` custom handler, used everywhere instead of `HTTPException` |
| Notification service dependency cycle | Stub created early, router/remaining methods added later |
| Missing `auth_client_teacher` fixture | Defined in conftest alongside `seed_teacher`, `seed_inactive_user` |
| `api/client.ts` circular import | Replaced with lazy `await import()` pattern |
| `/auth/refresh` doesn't check `is_active` | Added DB lookup in refresh endpoint |
