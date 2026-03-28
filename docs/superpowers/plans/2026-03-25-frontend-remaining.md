# Frontend Remaining Features Implementation Plan

**Goal:** Implement the 5 missing frontend features — radar chart, feedback page, counseling page, dashboard page, and Excel/PDF export — then wire all routes and polish the sidebar.

**Architecture:** API functions in `src/api/`, TanStack Query hooks in `src/hooks/`, pages in `src/pages/`, shared components in `src/components/`. Types extend `src/types/index.ts`. Routes registered in `App.tsx`.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query v5, Zustand, Recharts, xlsx, jsPDF

---

## Status — 2026-03-26 (All Complete)

| Task | File(s) | Status |
|------|---------|--------|
| 1. Feedback & Counseling types | `src/types/index.ts` | ✅ |
| 2. Feedback API + hook | `src/api/feedbacks.ts`, `src/hooks/useFeedbacks.ts` | ✅ |
| 3. Counseling API + hook | `src/api/counselings.ts`, `src/hooks/useCounselings.ts` | ✅ |
| 4. Radar chart + GradesPage tab | `src/components/grades/RadarChart.tsx`, `src/pages/GradesPage.tsx` | ✅ |
| 5. Feedback page | `src/pages/FeedbackPage.tsx` | ✅ |
| 6. Counseling page | `src/pages/CounselingPage.tsx` | ✅ |
| 7. Dashboard page | `src/pages/DashboardPage.tsx` | ✅ |
| 8. Excel / PDF export | `src/utils/exportHelpers.ts` | ✅ |
| 9. Wire routes + sidebar active states | `src/App.tsx`, `src/components/layout/Sidebar.tsx` | ✅ |
| 10. Smoke test + backend regression | — | ✅ |

---

## Remaining / Follow-up

- **UX polish:** Replace raw UUID inputs in Feedback/Counseling forms with a student selector dropdown; add form validation and toast notifications on success/error.
- **Export:** Wire Excel/PDF export buttons in `StudentListPage` (bulk) and `GradesPage` (per-student).
- **Accessibility:** Audit focus states, ARIA landmarks, and semantic labels across all new pages.
- **Responsive:** Final responsive tweaks for mobile sidebar overlay.
