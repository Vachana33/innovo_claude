# Implementation Plan — v2 Project-Centered Architecture

> **Status:** Ready for implementation. Documentation stack verified 2026-03.
> **Reference:** `SYSTEM_ARCHITECTURE.md` — full technical design.
> **Reference:** `PRODUCT_REQUIREMENTS.md` — workflows and data models.
> **Reference:** `docs/PRODUCT_VISION.md` — product philosophy.

---

## Execution Rules

**Phases must be implemented sequentially.** Each phase has a defined completion criterion that must be verified before the next phase begins. The system must be deployable and fully functional at the end of every phase. No phase leaves the codebase in a broken state.

**Existing endpoints are never broken.** All pre-v2 documents, companies, funding programs, and documents created before this migration must continue to work throughout all six phases and after completion.

**No phase rewrites existing modules.** Every phase is additive. Extraction of logic from `documents.py` into `PromptBuilder` (Phase 3) is a structural move, not a rewrite — prompt wording, LLM parameters, and output contracts are unchanged.

**The backward compatibility fallback is permanent.** Documents with `project_id = NULL` must always generate correctly via the direct `Company`/`FundingProgram` assembly path. This fallback is not removed after v2 is complete.

---

## Phase 1 — Project Entity

### Goal

Introduce `Project` as the first-class coordination entity. Users can create a project from a single form and be placed immediately in a project workspace. The workspace is a functional shell — context assembly and generation still use the existing v1 path. No existing behaviour changes.

This phase is the foundation for all subsequent phases. It must be complete before any service layer work begins.

---

### Backend Tasks

1. **New Alembic migration** — add the following tables and columns:
   - `projects` table (see `PRODUCT_REQUIREMENTS.md §4.5` for full schema)
   - `project_contexts` table (shell only — all JSON fields nullable, `assembled_at` null)
   - `project_id` nullable UUID FK column on `documents`
   - No changes to any existing table columns or constraints

2. **`backend/app/models.py`** — add `Project` and `ProjectContext` ORM models. No modifications to existing models.

3. **`backend/app/routers/projects.py`** — new file. Endpoints:
   - `POST /projects` — create project (validates company_id, funding_program_id, topic; resolves template via `template_resolver.py`; creates empty `Document` scoped to project; returns project)
   - `GET /projects` — list projects for current user (most recent 10 + pagination)
   - `GET /projects/{id}` — get project + context status
   - `PUT /projects/{id}` — update project name or topic
   - `DELETE /projects/{id}` — delete project (does not cascade-delete documents)

4. **`backend/main.py`** — register the `projects` router; add `projects` to the SPA catch-all skip list.

5. **`backend/app/schemas.py`** — add Pydantic request/response schemas for Project and ProjectContext.

---

### Frontend Tasks

1. **`frontend/src/pages/DashboardPage/`** — replace current entity-overview content with a project list. Each row: project name, status badge, funding program name, company name, last updated. Add search bar (client-side filter on project name). Add "New Project" button → `/projects/new`. Add archive toggle (filter by `status === "complete"`).

2. **`frontend/src/pages/NewProjectPage/`** — new page. Three required fields: Company (typeahead search or free-text create-new), Funding Program (select from loaded list), Topic (free text). One optional expandable section: website URL, file upload, audio upload. Single action button: "Start Analysis" → `POST /projects` → on success, navigate to `/projects/:id`.

3. **`frontend/src/pages/ProjectWorkspacePage/`** — new page. On mount: `GET /projects/:id`. Renders: project header (name, status), section sidebar (from resolved template), section editor (placeholder "Generate Content" button), context panel (shows `project.status`; for Phase 1 this is always `"ready"` — context assembly is not yet wired). All state is local to this page.

4. **`frontend/src/App.tsx`** — add routes: `/projects/new` → `NewProjectPage`, `/projects/:id` → `ProjectWorkspacePage`. Both wrapped in `ProtectedRoute`.

5. **`frontend/src/components/Layout.tsx`** — add "Projects" as a navigation item pointing to `/dashboard`. Do not remove any existing nav items in this phase.

---

### Files Changed

| File | Change type |
|------|-------------|
| `backend/alembic/versions/<new>.py` | New migration |
| `backend/app/models.py` | Add models (additive) |
| `backend/app/schemas.py` | Add schemas (additive) |
| `backend/app/routers/projects.py` | New file |
| `backend/main.py` | Register router + update skip list |
| `frontend/src/pages/DashboardPage/` | Update existing page |
| `frontend/src/pages/NewProjectPage/` | New page |
| `frontend/src/pages/ProjectWorkspacePage/` | New page |
| `frontend/src/App.tsx` | Add two routes (additive) |
| `frontend/src/components/Layout.tsx` | Add nav item (additive) |

**Files not touched:** `documents.py`, `companies.py`, `funding_programs.py`, `templates.py`, `extraction.py`, `preprocessing.py`, `EditorPage.tsx`, `CompaniesPage.tsx`, `FundingProgramsPage.tsx`.

---

### Compatibility Guarantees

- All existing API endpoints remain unchanged.
- All pre-v2 documents continue to work — `project_id` is nullable; existing documents have `project_id = NULL`.
- The v1 workflow (Companies → Funding Programs → Documents) remains fully functional.
- Generation behaviour is unchanged — `PromptBuilder` is not wired in this phase.

---

### Completion Criteria

- [ ] A user can log in, see the project dashboard, click "New Project", fill the three-field form, and land in a project workspace.
- [ ] The workspace shows the section list derived from the resolved template.
- [ ] `GET /projects` returns the user's projects in descending creation order.
- [ ] `GET /projects/:id` returns the project with `status: "ready"` (no context assembly yet).
- [ ] A document row with `project_id` set exists in the database after project creation.
- [ ] All existing endpoints (`/companies`, `/documents`, `/funding-programs`) return correct responses.
- [ ] The migration runs cleanly on a database with existing data (`alembic upgrade head`).

---

## Phase 2 — Context Assembler

### Goal

Wire context assembly into the project creation lifecycle. When a project is created, a background task runs the 5-stage pipeline, writes per-stage progress to `assembly_progress_json` (JSONB), detects company discovery success or failure, calculates a completeness score, and **always** sets `status = "ready"`. The workspace displays live assembly progress and shows a company fallback prompt when discovery fails.

This phase is the bridge between the Project entity and the generation pipeline. It must be complete before Phase 3 begins.

---

### Pre-Phase 2 — Phase 1 Bug Fixes (required before implementation)

| File | Bug | Fix |
|------|-----|-----|
| `backend/app/models.py` | `Project.company_id` and `funding_program_id` declared as `Column(String)` — should be `Column(Integer)` | Change to Integer |
| `backend/app/routers/projects.py` | `create_project` sets `status="pending"` | Change to `status="assembling"` |
| `frontend/.../DashboardPage.tsx` | `company_id`/`funding_program_id` typed as `string \| null` | Change to `number \| null` |
| `frontend/.../ProjectWorkspacePage.tsx` | Same type issue; `STATUS_LABELS` includes `"failed"`, missing `"generating"`/`"complete"` | Fix types; update STATUS_LABELS |
| `frontend/.../NewProjectPage.tsx` | Company input is a dropdown (`company_id` FK) | Replace with text input for `company_name` |

---

### Backend Tasks

1. **New Alembic migration — `a4b5c6d7e8f9_update_projects_v2_schema`**
   - `projects` table: add `company_name TEXT nullable`, `template_overrides_json TEXT nullable`
   - `project_contexts` table: add `completeness_score INTEGER nullable`, `company_discovery_status VARCHAR nullable`, `assembly_progress_json JSONB nullable`
   - `users` table: add `is_admin BOOLEAN NOT NULL DEFAULT false`
   - Chains from `a3b4c5d6e7f8`

2. **`backend/app/models.py`** — add new columns to `Project`, `ProjectContext`, `User`. Use `JSON` as ORM type for `assembly_progress_json` (SQLite dev compat); migration uses `JSONB`.

3. **`backend/app/schemas.py`** — extend:
   - `ProjectCreate`: add `company_name: Optional[str] = None`
   - `ProjectUpdate`: add `company_name`, `template_overrides_json`
   - `ProjectResponse` and `ProjectListItem`: add `company_name`
   - `ProjectContextResponse`: add `completeness_score`, `company_discovery_status`, `assembly_progress_json`

4. **`backend/app/services/__init__.py`** — create `services/` directory with empty `__init__.py`.

5. **`backend/app/services/context_assembler.py`** — new file:
   - Function: `assemble_project_context(project_id: str, db_url: str)` — creates own `SessionLocal()`
   - Constants:
     ```python
     CONTEXT_SCORE_WEIGHTS = {
         "company": 25, "funding_rules": 25,
         "domain_research": 20, "examples": 15, "style": 15,
     }
     ```
   - Stage 1 — Company research: use `project.company_id` profile if available; else web-search `project.company_name`; set `company_discovery_status` (`"found"` / `"partial"` / `"not_found"`)
   - Stage 2 — Funding rules: load guidelines for `project.funding_program_id`
   - Stage 3 — Domain research: web search on `project.topic`; summarise before storing; best-effort (empty = not an error)
   - Stage 4 — Historical examples: stub for Phase 2 (empty); updated in Phase 4
   - Stage 5 — Style profile: load most recent `alte_vorhabensbeschreibung_style_profile` for `user_email`
   - Each stage writes to `assembly_progress_json[stage_key]` before and after execution
   - Consolidation: calculate `completeness_score` from weights; set `project.status = "ready"` unconditionally

6. **`backend/app/routers/projects.py`** — additions:
   - `POST /projects`: accept `company_name`; dispatch `assemble_project_context` as `BackgroundTask` after commit
   - `POST /projects/{id}/context/refresh`: re-triggers assembler (sets status to `"assembling"` first)
   - `PATCH /projects/{id}/context`: merges `company_website`/`company_description` into `company_profile_json`; appends `"source": "user_provided"`; recalculates `completeness_score`; does not re-run full assembler

7. **`backend/app/routers/funding_programs.py`** — admin gate: check `current_user.is_admin` on `POST`, `PUT`, `DELETE`. Return `HTTP 403` for non-admin.

---

### Frontend Tasks

1. **`NewProjectPage.tsx`** — replace company `<select>` with `<input type="text">` for `company_name`; remove `GET /companies` fetch; `funding_program_id` remains required `<select>`

2. **`ProjectWorkspacePage.tsx`** — while `status === "assembling"`: render per-stage progress from `assembly_progress_json`; when `status === "ready"` and `company_discovery_status === "not_found"`: render fallback card with prompt for website/description; completeness indicator from `completeness_score`; fix TypeScript types

3. **`DashboardPage.tsx`** — fix TypeScript types: `company_id: number | null`, `funding_program_id: number | null`

---

### Files Changed

| File | Change type |
|------|-------------|
| `backend/alembic/versions/a4b5c6d7e8f9_update_projects_v2_schema.py` | New migration |
| `backend/app/models.py` | Add columns; fix Integer types on company_id/funding_program_id |
| `backend/app/schemas.py` | Extend schemas |
| `backend/app/services/__init__.py` | New directory + file |
| `backend/app/services/context_assembler.py` | New service |
| `backend/app/routers/projects.py` | BackgroundTask + PATCH context + refresh endpoints |
| `backend/app/routers/funding_programs.py` | Admin gate |
| `frontend/src/pages/NewProjectPage/NewProjectPage.tsx` | Replace company dropdown with text input |
| `frontend/src/pages/ProjectWorkspacePage/ProjectWorkspacePage.tsx` | Progress, fallback, completeness, type fixes |
| `frontend/src/pages/DashboardPage/DashboardPage.tsx` | TypeScript type fix |

**Files not touched:** `documents.py`, `companies.py`, `extraction.py`, `preprocessing.py`, `guidelines_processing.py`, `style_extraction.py`, `EditorPage.tsx`, `CompaniesPage.tsx`, `FundingProgramsPage.tsx`.

---

### Compatibility Guarantees

- All pre-v2 documents (`project_id = NULL`) continue to generate via the v1 path. Unchanged.
- Existing `process_company_background` task is not modified. The assembler reads the same DB fields but does not replace this task.
- If a company record already has `company_profile` set, Stage 1 reads it and skips web search.
- All new columns are nullable or have safe server defaults — existing rows unaffected.
- Admin gate only restricts write endpoints; reads remain open.

---

### Completion Criteria

- [ ] Creating a project immediately sets `status = "assembling"` and triggers the assembler as a BackgroundTask
- [ ] Frontend shows per-stage progress from `assembly_progress_json` while `status === "assembling"`
- [ ] Polling stops correctly when `status === "ready"` and clears on page navigation
- [ ] All projects reach `status = "ready"` even when all web research stages return empty
- [ ] `completeness_score` is present on every assembled context (0–100)
- [ ] `company_discovery_status` is one of `"found"` / `"partial"` / `"not_found"` on every context
- [ ] Company fallback prompt appears in workspace when `company_discovery_status === "not_found"`
- [ ] `PATCH /projects/:id/context` merges provided data without overwriting existing profile
- [ ] Non-admin users receive HTTP 403 on funding program mutation endpoints
- [ ] `POST /projects` body accepts `company_name`; NewProjectPage uses text input not dropdown
- [ ] All pre-v2 documents and v1 workflow remain fully functional

---

## Phase 3 — PromptBuilder

### Goal

Extract all prompt assembly logic from `documents.py` into `services/prompt_builder.py`. Generation endpoints call `PromptBuilder` with a `ProjectContext` if one exists, or fall back to direct assembly if `project_id` is null. Prompt wording, block order, LLM parameters, and output contracts are unchanged.

This is the highest-risk structural phase because it touches the core generation path. It must be implemented carefully and verified with test generations before deployment.

---

### Backend Tasks

1. **`backend/app/services/prompt_builder.py`** — new file. Class `PromptBuilder`. Constructor accepts either:
   - `ProjectContext` object (v2 path)
   - `company: Company`, `funding_rules: dict`, `style_profile: dict` (v1 fallback path, all optional)

   Methods:
   - `build_generation_prompt(sections: list) -> str` — assembles six-block prompt (see `SYSTEM_ARCHITECTURE.md §5.3`)
   - `build_edit_prompt(section, instruction, current_content) -> str` — assembles edit prompt
   - `build_qa_prompt(document_text, website_summary, conversation_history, user_query) -> str` — assembles Q&A prompt

   `PromptBuilder` has no I/O. It makes no database calls. It is a pure function object.

2. **`backend/app/routers/documents.py`** — update three functions only:
   - `_generate_batch_content()` — before building the prompt: attempt `db.query(ProjectContext).filter_by(project_id=doc.project_id).first()`. If found, construct `PromptBuilder(context=project_context)`. If not found (or `doc.project_id` is null), construct `PromptBuilder(company=company, funding_rules=rules, style_profile=style)`. Call `PromptBuilder.build_generation_prompt(sections)`. Replace the existing inline prompt string with the result.
   - `_generate_section_content()` — same pattern; call `PromptBuilder.build_edit_prompt(...)`.
   - `_answer_question_with_context()` — same pattern; call `PromptBuilder.build_qa_prompt(...)`.

   The inline prompt construction code is removed from these three functions only. No other changes to `documents.py`.

---

### Frontend Tasks

None. This phase is backend-only.

---

### Files Changed

| File | Change type |
|------|-------------|
| `backend/app/services/prompt_builder.py` | New file |
| `backend/app/routers/documents.py` | Modify three functions (extract prompt assembly) |

---

### Compatibility Guarantees

- Prompt wording within each block is **not changed** — copied verbatim from current `documents.py` into `PromptBuilder` methods.
- Prompt block order is **not changed** — existing four blocks remain in position; two new blocks are inserted between block 2 and the existing block 3 (Stil-Leitfaden).
- v1 fallback path (`project_id = NULL`) assembles identical prompts to the current system.
- LLM model, temperature, max_tokens, timeout, and retry logic are **not changed**.
- `milestone_table` skip guard is **not changed** — still enforced before `PromptBuilder` is called.
- XML delimiter injection for `instruction` and `user_query` is **not changed** — moved into `PromptBuilder` methods.
- Token logging is **not changed** — moved into `PromptBuilder` methods, called before each API call.

---

### Completion Criteria

- [ ] Generate content on a pre-v2 document (no `project_id`) — output is identical in structure to pre-Phase-3 output.
- [ ] Generate content on a v2 project document (with `project_context`) — output uses `ProjectContext` fields.
- [ ] Edit a section via chat — output is correct; section titles are not modified.
- [ ] Ask a question via chat — answer is returned correctly.
- [ ] Token logging appears in logs for all three generation paths.
- [ ] `documents.py` diff shows only removal of inline prompt construction from the three target functions. No other lines changed.

---

## Phase 3B — Chatbot Assistant

### Goal

Replace the static section-level chat interface with a project-scoped chatbot assistant. The assistant reads the current `ProjectContext` as system context, maintains a conversation history per project, and can write corrections back to context fields based on user input. This is the primary quality-control mechanism for incomplete context.

This phase depends on Phase 3 (PromptBuilder must be wired) and Phase 2 (ProjectContext must exist). It runs after Phase 3 is complete.

---

### Backend Tasks

1. **New Alembic migration** — add `project_chat_messages` table:
   - `id`: VARCHAR PK
   - `project_id`: VARCHAR FK → `projects.id` ON DELETE CASCADE
   - `role`: VARCHAR (`"user"` or `"assistant"`)
   - `content`: TEXT
   - `created_at`: DATETIME server_default now()
   - Index: `ix_project_chat_messages_project_id`

2. **`backend/app/models.py`** — add `ProjectChatMessage` ORM model.

3. **`backend/app/schemas.py`** — add `ProjectChatMessageCreate`, `ProjectChatMessageResponse`, `ProjectChatHistoryResponse`.

4. **`backend/app/services/project_chat_service.py`** — new file:
   - `handle_user_message(project_id, user_message, db)` — load `ProjectContext`, build system prompt from context, call LLM, parse response
   - If response contains context corrections: update `company_profile_json` (merge, same pattern as `PATCH /context`), recalculate `completeness_score`
   - Persist both user and assistant messages to `project_chat_messages`
   - Return assistant response text

5. **`backend/app/routers/project_chat.py`** — new file:
   - `GET /projects/{id}/chat` — return full message history
   - `POST /projects/{id}/chat` — accept `{ message: string }`, call `project_chat_service.handle_user_message()`, return assistant response

6. **`backend/main.py`** — register `project_chat` router; add `"projects"` to SPA skip list already covers this since the router uses the `/projects` prefix.

---

### Frontend Tasks

1. **`ProjectWorkspacePage.tsx`** — add chatbot panel below the generate section:
   - Load conversation history from `GET /projects/:id/chat` on mount
   - Render message list (user and assistant bubbles)
   - Text input + send button → `POST /projects/:id/chat`
   - On response: append to message list; if `completeness_score` updated, refresh project context panel

---

### Files Changed

| File | Change type |
|------|-------------|
| `backend/alembic/versions/<new>.py` | New migration (project_chat_messages) |
| `backend/app/models.py` | Add ProjectChatMessage model |
| `backend/app/schemas.py` | Add chat schemas |
| `backend/app/services/project_chat_service.py` | New service |
| `backend/app/routers/project_chat.py` | New router |
| `backend/main.py` | Register router |
| `frontend/src/pages/ProjectWorkspacePage/ProjectWorkspacePage.tsx` | Add chatbot panel |

**Files not touched:** `documents.py`, existing document-level `chat_history` column is unchanged.

---

### Compatibility Guarantees

- Document-level chat (`POST /documents/{id}/chat`) is unchanged.
- Existing `chat_history` JSON column on documents is not touched.
- The chatbot only writes to `project_contexts.company_profile_json` — no other context fields are modified by user messages.

---

### Completion Criteria

- [ ] `GET /projects/:id/chat` returns conversation history in order
- [ ] `POST /projects/:id/chat` returns assistant response within 30s
- [ ] Assistant response reads company and funding context from `ProjectContext`
- [ ] User corrections to company info (e.g. "The company builds welding robots") are merged into `company_profile_json`
- [ ] `completeness_score` is recalculated after context writes
- [ ] Chatbot panel renders in workspace and maintains scroll position
- [ ] Document-level chat is unaffected

---

## Phase 4 — Knowledge Base

### Goal

Introduce the knowledge base infrastructure. Admin users can upload past applications, domain documents, and supplementary files. Documents are chunked, embedded, and stored for semantic retrieval. `context_assembler.py` retrieves relevant chunks into `retrieved_examples_json` during Stage 3 of project initialisation. `PromptBuilder` injects them as block 4 (Referenzbeispiele).

---

### Backend Tasks

1. **New Alembic migration** — add `knowledge_base_documents` and `knowledge_base_chunks` tables (see `SYSTEM_ARCHITECTURE.md §6.3`). Requires `pgvector` extension on PostgreSQL (`CREATE EXTENSION IF NOT EXISTS vector`).

2. **`backend/app/models.py`** — add `KnowledgeBaseDocument` and `KnowledgeBaseChunk` ORM models.

3. **`backend/app/services/knowledge_base_retriever.py`** — new file. Functions:
   - `index_document(document_id, db)` — chunk document text by section, embed each chunk via `text-embedding-3-small`, store in `knowledge_base_chunks`.
   - `retrieve_similar_chunks(query: str, program_tag: str, top_k: int, db) -> list` — embed query, run pgvector cosine similarity search, return top-k chunks. Cap `top_k` at 3.

4. **`backend/app/routers/knowledge_base.py`** — new file. Admin-only endpoints:
   - `POST /knowledge-base/documents` — upload document (PDF/DOCX), extract text, create `KnowledgeBaseDocument`, trigger indexing as `BackgroundTask`.
   - `GET /knowledge-base/documents` — list documents by category.
   - `DELETE /knowledge-base/documents/{id}` — delete document and associated chunks.

5. **`backend/main.py`** — register the `knowledge_base` router; add `knowledge-base` to the SPA skip list.

6. **`backend/app/services/context_assembler.py`** — update Stage 3: call `knowledge_base_retriever.retrieve_similar_chunks(query=f"{project.topic} {company.name}", program_tag=funding_program_tag, top_k=3, db=db)`. Store result as `project_context.retrieved_examples_json`.

7. **`backend/app/services/prompt_builder.py`** — update `build_generation_prompt()`: if `retrieved_examples_json` is non-empty, inject block 4 (Referenzbeispiele). If empty, skip the block (do not inject an empty section header).

---

### Frontend Tasks

None for the primary user flow. The knowledge base is admin-managed, not user-facing. If an admin panel is required, it can be accessed via a separate route not in primary navigation.

---

### Files Changed

| File | Change type |
|------|-------------|
| `backend/alembic/versions/<new>.py` | New migration |
| `backend/app/models.py` | Add models (additive) |
| `backend/app/routers/knowledge_base.py` | New file |
| `backend/app/services/knowledge_base_retriever.py` | New file |
| `backend/app/services/context_assembler.py` | Update Stage 3 |
| `backend/app/services/prompt_builder.py` | Add block 4 injection |
| `backend/main.py` | Register router + update skip list |

---

### Compatibility Guarantees

- `retrieved_examples_json` is nullable. If the knowledge base is empty, Stage 3 stores `null` and `PromptBuilder` omits block 4. Generation quality is unchanged from Phase 3.
- The pgvector migration must be applied to production PostgreSQL before deployment. SQLite development environments skip the vector column gracefully (column type falls back to Text; retrieval queries are not executed if no chunks exist).
- Existing generation pipeline is unchanged.

---

### Completion Criteria

- [ ] An admin can upload a past Vorhabensbeschreibung PDF via `POST /knowledge-base/documents`.
- [ ] The document is chunked and embedded in the background.
- [ ] `GET /knowledge-base/documents` lists the uploaded document.
- [ ] A new project with a matching topic and funding program retrieves chunks from the knowledge base.
- [ ] `project_context.retrieved_examples_json` is populated after context assembly.
- [ ] Generation output for a v2 project includes the Referenzbeispiele block in the prompt (verifiable via token logging).
- [ ] A project with no matching knowledge base documents generates correctly with no Referenzbeispiele block.

---

## Phase 5 — Research Agent

### Goal

Introduce automatic domain and company research for projects where company information is insufficient. `research_agent.py` makes structured web search queries and stores the results as `domain_research_json` in `ProjectContext`. `PromptBuilder` injects this as block 3 (Projektthema und Domäne).

**Security gate:** RFC 1918 URL validation must be implemented and verified before this phase is deployed to production. See `SYSTEM_ARCHITECTURE.md §7.4` and `.claude/agents/security_agent.md`.

---

### Backend Tasks

1. **`backend/app/services/research_agent.py`** — new file. Function: `research_project_context(company_name, topic, db_url) -> dict`. Executes three targeted search queries (company context, domain state-of-art, competitive landscape). Summarises results via a single LLM call before storing. Returns structured `domain_research_json`. All outbound HTTP requests go to the search API's fixed base URL only. Validates that the search API URL is not in RFC 1918 ranges before any connection.

2. **`backend/app/services/context_assembler.py`** — update Stage 4: trigger `research_agent.research_project_context()` only when `company.company_profile` is null AND `company.website` is null AND `company.transcript_clean` is null. Store result as `project_context.domain_research_json`.

3. **`backend/app/services/prompt_builder.py`** — update `build_generation_prompt()`: if `domain_research_json` is non-empty, inject block 3 (Projektthema und Domäne). If empty, inject a minimal topic block using `project.topic` only.

4. **Environment variable** — `WEB_SEARCH_API_KEY` added to the environment variable list in `PRODUCT_REQUIREMENTS.md §6.6`. Optional — if absent, Stage 4 is skipped silently.

---

### Frontend Tasks

1. **`ProjectWorkspacePage` context panel** — add a "Domain Research" row. Show status: loading (during assembly), present (if `domain_research_json` populated), or "not performed" (if company already had sufficient data).

---

### Files Changed

| File | Change type |
|------|-------------|
| `backend/app/services/research_agent.py` | New file |
| `backend/app/services/context_assembler.py` | Update Stage 4 |
| `backend/app/services/prompt_builder.py` | Add block 3 injection |
| `frontend/src/pages/ProjectWorkspacePage/` | Update context panel |

---

### Compatibility Guarantees

- Research is only triggered for new companies with no existing data. Existing company records are unaffected.
- If `WEB_SEARCH_API_KEY` is absent, Stage 4 is skipped. Projects still assemble and generate correctly.
- `domain_research_json` is nullable. An absent value causes `PromptBuilder` to inject a minimal topic block using `project.topic` text only.
- Research results pass through LLM summarisation before storage. Raw web content never reaches the generation prompt.

---

### Completion Criteria

- [ ] `WEB_SEARCH_API_KEY` absent → Stage 4 skipped, no error logged.
- [ ] `WEB_SEARCH_API_KEY` present, new company with no data → research runs and `domain_research_json` is populated.
- [ ] `WEB_SEARCH_API_KEY` present, company with existing profile → Stage 4 skipped.
- [ ] Generation prompt for a researched project includes block 3 content derived from domain research.
- [ ] Security review passed: outbound request target is the fixed search API URL only; RFC 1918 validation confirmed.
- [ ] Logging confirms no raw web content is logged.

---

## Phase 6 — Navigation Simplification

### Goal

Simplify the primary navigation to match the ChatGPT-style interface described in `docs/PRODUCT_VISION.md`. Old entity management pages are moved out of the primary nav and into settings. No routes are removed.

This phase is frontend-only. It has no backend changes.

---

### Frontend Tasks

1. **`frontend/src/components/Layout.tsx`** — primary navigation becomes two items only: **Projects** (`/dashboard`) and **Settings** (dropdown or settings page). Remove Companies, Funding Programs, Documents, Templates from the primary nav bar.

2. **Settings access** — the removed nav items become accessible via:
   - A settings dropdown or settings page in the nav
   - Or direct URL navigation (routes remain functional)
   - Minimum requirement: users must be able to reach `/companies`, `/funding-programs`, `/templates` without memorising URLs.

3. **`frontend/src/pages/DashboardPage/`** — ensure empty state is handled gracefully: if the user has no projects, show a prominent "Create your first project" call to action, not an empty list.

4. **`frontend/src/pages/ProjectWorkspacePage/`** — replace the 2-second hardcoded poll interval (inherited from `EditorPage`) with the 3-second backoff polling implemented in Phase 2. Verify clean interval teardown on unmount.

---

### Files Changed

| File | Change type |
|------|-------------|
| `frontend/src/components/Layout.tsx` | Simplify nav |
| `frontend/src/pages/DashboardPage/` | Add empty state |
| `frontend/src/pages/ProjectWorkspacePage/` | Verify polling behaviour |

**Files not removed:** All existing page files remain. All existing routes remain registered in `App.tsx`.

---

### Compatibility Guarantees

- No routes are removed. All existing pages remain accessible via direct URL.
- The `EditorPage` at `/editor/:companyId/:docType` remains functional and accessible from the project workspace.
- Users who bookmarked `/companies` or `/documents` continue to reach those pages.

---

### Completion Criteria

- [ ] Primary navigation shows only two items: Projects and Settings.
- [ ] All entity management pages (`/companies`, `/funding-programs`, `/templates`) are reachable from Settings.
- [ ] Dashboard empty state directs new users to create a project.
- [ ] Polling in the workspace tears down cleanly on navigation (no stale intervals).
- [ ] No console errors on any existing route after nav change.

---

## Phase Summary

| Phase | Core change | Backend | Frontend | Blocks next phase? |
|-------|-------------|---------|----------|--------------------|
| 1 | Project entity | models, migration, router | Dashboard, NewProject, Workspace shell | Yes — all phases depend on Project existing |
| 2 | Context assembler + admin gate | migration, context_assembler.py, PATCH context, admin gate | Progress UI, fallback prompt, completeness indicator, company_name input | Yes — Phase 3 reads from ProjectContext |
| 3 | PromptBuilder | services/prompt_builder.py, documents.py (3 functions) | None | Yes — Phases 3B, 4, 5 extend PromptBuilder |
| 3B | Chatbot assistant | migration, project_chat_service.py, project_chat.py | Chatbot panel in workspace | No — independent of 4 and 5 |
| 4 | Knowledge base | migration, retriever, KB router | None | No — Phase 5 is independent |
| 5 | Research agent | research_agent.py | Context panel update | No — Phase 6 is independent |
| 6 | Nav simplification | None | Layout, Dashboard | No — terminal phase |

---

## Pre-Implementation Checklist

Before beginning Phase 1:

- [ ] `SYSTEM_ARCHITECTURE.md` reviewed and understood
- [ ] `PRODUCT_REQUIREMENTS.md §4.5` schema understood
- [ ] `DEVELOPMENT_RULES.md` v2 migration exception noted
- [ ] `CLAUDE.md` v2 exception noted
- [ ] Alembic migration chain (`backend/alembic/versions/`) reviewed — identify the current `head` revision to ensure the new migration chains correctly
- [ ] PostgreSQL `pgvector` extension availability confirmed for production (needed in Phase 4)
- [ ] `backend/app/routers/documents.py` — confirm current `head` revision in the file before touching it in Phase 3
- [ ] Security agent consulted before Phase 5 implementation begins
