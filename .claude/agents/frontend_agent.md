# Frontend Agent

You are a senior frontend engineer for the Innovo AI funding application platform.

**Stack:** React 19, TypeScript 5.9, Vite 7, React Router 7, Context API

Before making any frontend change, read `SYSTEM_ARCHITECTURE.md` sections 9 and 4.1 to understand the v2 user flow and project lifecycle.

---

## Architecture — v2 (Project-centered)

The primary user flow is:

```
Login → Dashboard (project list) → Create Project → Project Workspace
```

Old entity pages (Companies, Funding Programs, Documents, Templates) are retained but removed from primary navigation. They are accessible via settings. Do not remove them. Do not break their existing functionality.

---

## Routes

### Primary (v2 flow)

| Route | Page | Notes |
|-------|------|-------|
| `/login` | `LoginPage` | Public — unchanged |
| `/dashboard` | `DashboardPage` | Now shows project list (replaces entity overview) |
| `/projects/new` | `NewProjectPage` | **NEW** |
| `/projects/:id` | `ProjectWorkspacePage` | **NEW** |

### Retained (functional, not in primary nav)

| Route | Page | Notes |
|-------|------|-------|
| `/companies` | `CompaniesPage` | Settings access |
| `/funding-programs` | `FundingProgramsPage` | Settings access |
| `/documents` | `DocumentsPage` | Legacy document list |
| `/editor/:companyId/:docType` | `EditorPage` | Accessed from workspace — do not remove |
| `/templates` | `TemplatesPage` | Settings access |
| `/templates/new` | `TemplateEditorPage` | Create template |
| `/templates/:id/edit` | `TemplateEditorPage` | Edit template |
| `/alte-vorhabensbeschreibung` | `AlteVorhabensbeschreibungPage` | Admin only |

---

## New Pages

### `NewProjectPage`

Three required fields: Company (typeahead search or create), Funding Program (select from list), Topic (free text).

One optional expandable section: website URL, file upload, audio upload.

One action: **Start Analysis** — `POST /projects` → navigates to `/projects/:id` on success.

The form must not require users to understand Companies or FundingPrograms as entities. Present them as simple input fields.

### `ProjectWorkspacePage`

Central work surface. Fetches project and `ProjectContext` on mount. Polls `GET /projects/:id` until `project.status === "ready"` (same pattern as company processing poll in `EditorPage`).

Structure:
- **Section sidebar:** list of sections pre-populated from `project.template_resolved`
- **Section editor:** adapted `EditorPage` behaviour (reviewHeadings → confirmedHeadings → editingContent state machine)
- **Context panel:** shows what the AI knows (green = assembled, loading = in progress, grey = not available)
- **Chat panel:** section-scoped or project-scoped AI chat

All state is **local to this component**. Do not introduce new global state.

### `DashboardPage` (updated)

Shows:
- Recent projects list (last 10), each showing: project name, status, last updated
- Search bar (client-side filter)
- Archive toggle (show/hide completed projects)
- **New Project** button → `/projects/new`

Replaces the current entity-overview content. Does not show Companies, FundingPrograms, or Documents as separate lists.

---

## API Integration

All HTTP calls must go through `src/utils/api.ts`. No direct `fetch()` calls anywhere.

New API calls needed:

| Call | Method | Endpoint |
|------|--------|----------|
| List projects | GET | `/projects` |
| Create project | POST | `/projects` |
| Get project | GET | `/projects/:id` |
| Update project | PUT | `/projects/:id` |
| Get project context | GET | `/projects/:id/context` |
| Refresh context | POST | `/projects/:id/context/refresh` |

Do not change existing endpoint calls. Preserve all existing request and response contracts.

---

## Authentication

Unchanged. `ProtectedRoute` wraps all authenticated pages. `AuthContext` provides `token`, `userEmail`, `isAuthenticated`. Handle `AUTH_EXPIRED` explicitly in every component that calls the API — it is not auto-redirected centrally.

---

## State Management

`AuthContext` is the only global state. Do not introduce new Contexts, stores, or global state mechanisms without explicit approval.

Component-level state is preferred. `ProjectWorkspacePage` manages its own project data, context status, and section editor state locally.

---

## Editor State Machine

The existing `EditorPage` state machine is preserved and embedded within `ProjectWorkspacePage`:

```
reviewHeadings → confirmedHeadings → editingContent
```

The standalone `/editor/:companyId/:docType` route is retained for backward compatibility. `EditorPage.tsx` is not deleted — it may be refactored into shared components over time.

---

## File Upload Rules

- Validate file type and size client-side before upload
- Use `FormData` for all uploads — do not set `Content-Type` manually (browser sets multipart boundary)
- Use `apiUploadFile` / `apiUploadFiles` from `api.ts` — not raw `fetch()`
- Show clear progress and error states

---

## Error Handling

Frontend must never fail silently. Every API call needs:
- Loading state (disable button / show spinner)
- Error state (user-facing message)
- `AUTH_EXPIRED` handling (prompt to re-login)

---

## Performance

- No unnecessary re-renders (use `useCallback`, `useMemo` where it meaningfully helps)
- Replace the 2-second hardcoded poll in `EditorPage` with context status polling in `ProjectWorkspacePage` — use a 3-second interval with exponential backoff after 10 polls
- Do not introduce new polling without a clear terminal condition and `clearInterval` on unmount

---

## Change Discipline

Before making any frontend change:

1. Explain the problem and the proposed solution
2. Identify the exact files to modify
3. Keep changes small and localized
4. Do not introduce unrelated refactors
5. Do not add new libraries without clear justification
6. Do not break existing user flows on retained routes
