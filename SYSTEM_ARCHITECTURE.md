# System Architecture — Innovo Claude

> **Audience:** AI agents and engineers making structural changes to this codebase.
> **Scope:** Technical implementation detail. For product purpose, see `PRODUCT_REQUIREMENTS.md`. For product philosophy, see `docs/PRODUCT_VISION.md`.
> **Version:** v2 — Project-centered architecture. Prior entity-centric design is described in git history.
> **Status:** Verified against source code 2026-03.

---

## 1. Process Model

The application runs as **a single Uvicorn process**. There is no separate worker, message broker, or job scheduler. Background work runs in-process via FastAPI's `BackgroundTasks`.

```
Single Uvicorn Process
├── FastAPI event loop (asyncio)
│   ├── HTTP request handlers (async)
│   ├── BackgroundTasks (sync functions scheduled post-response)
│   └── Lifespan hooks (PostHog init/shutdown)
└── SQLAlchemy session pool (sync, threadlocal)
```

**Thread ceiling constraint:** `BackgroundTasks` runs sync functions in Uvicorn's thread pool. Two long-running background tasks already exist: company processing (Whisper, up to minutes) and project context assembly (crawl + extraction chain). Do not add further long-running synchronous background tasks without acknowledging this constraint.

---

## 2. System Overview — v2 Architecture

### 2.1 The Central Concept

`Project` is the first-class entity that coordinates all other entities. A project binds a `Company`, a `FundingProgram`, and a body of work (`Documents`) under a single user-defined topic.

In v1, users assembled this binding manually by navigating between entity management screens. In v2, the system assembles it automatically from a single creation form.

```
User
 └─ Project
       ├─ company_id          FK → companies (shared, reusable)
       ├─ funding_program_id  FK → funding_programs (shared, reusable)
       ├─ topic               Free text: "Robot automation for weld seam tracking"
       ├─ status              initializing | context_loading | ready | generating | complete
       ├─ template_resolved   Stored at creation; never re-resolved
       ├─ ProjectContext       Assembled once; reused for all generation calls
       └─ documents           Documents scoped to this project
```

**Companies and FundingPrograms remain shared entities.** One company can belong to many projects. The Project layer is additive — no existing entity is removed or restructured.

### 2.2 What Changed from v1

| Aspect | v1 | v2 |
|--------|----|----|
| Entry point | Companies screen | Dashboard (project list) |
| Context assembly | Inline at generation time in `documents.py` | Pre-assembled into `ProjectContext` by `context_assembler.py` |
| Prompt construction | Scattered across `documents.py` | `services/prompt_builder.py` |
| Knowledge reuse | Style profile only (global, single type) | Knowledge base (multi-category, semantic retrieval) |
| Company research | Manual: user provides website or audio | Automatic: research agent fills gaps |
| Template selection | Manual: user selects at document creation | Automatic: inferred from FundingProgram at project creation |

**What did not change:** All existing API endpoints, response shapes, database columns, prompt wording, prompt block order, XML delimiter injection, and LLM call site locations.

---

## 3. Backend Architecture

### 3.1 Entry Point — `backend/main.py`

Startup sequence (order matters):

```
1.  Load .env (only if file exists — dev guard)
2.  Validate JWT_SECRET_KEY (RuntimeError if absent)
3.  Warn if OPENAI_API_KEY absent (soft fail)
4.  Parse DATABASE_URL, detect SQLite vs PostgreSQL
5.  If SQLite: run Base.metadata.create_all() (dev convenience)
6.  If PostgreSQL: skip create_all() (Alembic owns the schema)
7.  Instantiate FastAPI app with lifespan context manager
8.  Register CORSMiddleware
9.  Register exception handlers (HTTP, Validation, general)
10. Include all routers
11. Mount /assets static files
12. Register /health endpoint
13. Register SPA catch-all route (must be last)
```

**SPA catch-all skip list:** The catch-all `GET /{full_path:path}` skips paths starting with known API prefixes to avoid intercepting API routes. Current list: `auth/`, `funding-programs`, `companies`, `documents`, `templates`, `health`, `assets/`, `projects`, `knowledge-base`.

**Critical rule:** Every new router prefix must be added to this skip list. Omitting it causes the SPA to silently serve `index.html` for API calls in production.

### 3.2 Router Layout

All routers are registered on the root FastAPI app (no `/api` prefix).

| Router file | Prefix examples | Status |
|-------------|----------------|--------|
| `routers/auth.py` | `/auth/*` | Unchanged |
| `routers/companies.py` | `/companies`, `/companies/{id}` | Unchanged |
| `routers/funding_programs.py` | `/funding-programs`, `/funding-programs/{id}` | Unchanged |
| `routers/documents.py` | `/documents/{company_id}/{type}`, `/documents/{id}/generate-content`, `/documents/{id}/chat`, `/documents/{id}/export` | Updated: generation reads from ProjectContext via PromptBuilder |
| `routers/templates.py` | `/templates`, `/system-templates` | Unchanged |
| `routers/alte_vorhabensbeschreibung.py` | `/alte-vorhabensbeschreibung` | Unchanged (retained for backward compat) |
| `routers/projects.py` | `/projects`, `/projects/{id}` | **NEW** |
| `routers/knowledge_base.py` | `/knowledge-base` | **NEW** (admin-only) |

### 3.3 Service Layer — `backend/app/services/`

This directory is new in v2. Services contain business logic that was previously inline in routers or in `documents.py`.

**Architectural rule:** Routers call services. Services call existing modules (`extraction.py`, `preprocessing.py`, etc.). Services never call routers. Business logic does not live in routers.

| Service file | Responsibility |
|-------------|---------------|
| `context_assembler.py` | Background task: assembles `ProjectContext` from all available sources |
| `prompt_builder.py` | Constructs LLM prompts from `ProjectContext`; manages context budget |
| `research_agent.py` | Background task: web search enrichment when company data is absent |
| `knowledge_base_retriever.py` | Semantic similarity retrieval from `knowledge_base_chunks` (pgvector) |

### 3.4 Existing Modules — `backend/app/`

These modules are unchanged and called by services and routers.

| Module | Responsibility | Called by |
|--------|---------------|-----------|
| `extraction.py` | LLM extraction of company profile from text | `context_assembler.py`, `companies.py` |
| `preprocessing.py` | Website crawl, audio transcription (Whisper) | `context_assembler.py`, `companies.py` |
| `guidelines_processing.py` | Structured rule extraction from guideline PDFs | `context_assembler.py`, `funding_programs.py` |
| `style_extraction.py` | Writing style extraction from historical docs | `context_assembler.py`, `alte_vorhabensbeschreibung.py` |
| `file_storage.py` | Supabase upload, SHA-256 deduplication | All file-handling routers |
| `document_extraction.py` | Text extraction from PDFs/DOCX | `context_assembler.py`, `funding_programs.py` |
| `text_cleaning.py` | Boilerplate removal, filler word cleanup | `context_assembler.py`, `companies.py` |
| `processing_cache.py` | Hash-based cache read/write (no TTL) | All processing modules |
| `template_resolver.py` | Resolve template for a document | `projects.py` (at creation), `documents.py` |
| `observability.py` | Request tracking, structured logging | `main.py` middleware |
| `posthog_client.py` | Analytics event capture | `auth.py`, `main.py` |
| `jwt_utils.py` | Token generation and verification | `auth.py`, `dependencies.py` |
| `dependencies.py` | `get_current_user` FastAPI dependency | All protected routers |

### 3.5 Authentication

Unchanged from v1. Every protected endpoint uses the `get_current_user` dependency.

```
Request: Authorization: Bearer <jwt>
    │
    ▼
dependencies.py: get_current_user()
    │
    jwt_utils.py: verify_token()
    │
    ├── Valid   → DB lookup by email → return User
    └── Invalid → HTTP 401
```

JWT parameters: HS256, 24-hour access token, 1-hour password reset token.

### 3.6 Database Layer

Unchanged from v1. Development uses SQLite; production uses PostgreSQL with pool_size=5, max_overflow=10, pool_pre_ping=True.

Schema management: Alembic only in production. `Base.metadata.create_all()` is suppressed for PostgreSQL.

---

## 4. Project Lifecycle

### 4.1 Creation

```
POST /projects
    │
    ├── Validate: company_id, funding_program_id, topic (required)
    ├── Resolve template from FundingProgram → store as project.template_resolved
    ├── Create Project row (status: "initializing")
    ├── Create Document row (empty sections from resolved template)
    ├── Return project to client immediately
    └── BackgroundTask → assemble_project_context()
```

### 4.2 Context Assembly Pipeline

`context_assembler.py` runs as a background task in five sequential stages:

```
Stage 1 — Retrieve stored assets         (no LLM, fast)
    ├── Load company.company_profile_json (if exists)
    ├── Load funding_program_guidelines_summary.rules_json (if exists)
    └── Load alte_vorhabensbeschreibung_style_profile.style_summary_json (most recent)

Stage 2 — Enrich company context         (async, may call LLM)
    ├── If company has website: crawl → clean → cache (website_text_cache)
    ├── If company has audio: Whisper → clean → cache (audio_transcript_cache)
    ├── If company has uploaded docs: extract → clean → cache (document_text_cache)
    └── If any text available and no profile yet: extract_company_profile() → LLM

Stage 3 — Knowledge base retrieval       (pgvector query)
    └── knowledge_base_retriever.py: embed (topic + company name) → top-k chunks
        → retrieved_examples_json

Stage 4 — Domain research                (optional, web search)
    └── research_agent.py: triggered only if company has no profile and no website
        → domain_research_json

Stage 5 — Consolidate                    (assemble snapshot)
    ├── Merge all sources into ProjectContext
    ├── Compute context_hash
    └── Set project.status = "ready"
```

**Partial context is usable.** Generation can proceed with any combination of available context fields. Missing fields produce less accurate output; they do not cause errors.

### 4.3 Project Status Values

| Status | Set when |
|--------|---------|
| `initializing` | Project row created, context assembly not yet started |
| `context_loading` | Context assembly background task is running |
| `ready` | ProjectContext assembled; document generation is available |
| `generating` | Content generation in progress |
| `complete` | Document exported |

### 4.4 Context Invalidation

When the user uploads new company documents or new guideline files:
1. The relevant cache tables are updated (hash-based, as before)
2. `project.status` reverts to `context_loading`
3. `assemble_project_context()` is re-triggered
4. On completion, `ProjectContext` is updated and `project.status` returns to `ready`

---

## 5. Document Generation Pipeline

### 5.1 Context Input (v2)

Generation reads from `ProjectContext` via `PromptBuilder`. If no `ProjectContext` exists (documents created before v2, or documents not associated with a project), generation falls back to direct assembly from `Company` and `FundingProgram` rows — identical to v1 behaviour.

| Context field | Source | Used in |
|---------------|--------|---------|
| `company_profile_json` | `companies.company_profile` | All generation calls |
| `funding_rules_json` | `funding_program_guidelines_summary.rules_json` | Batch generation |
| `domain_research_json` | `research_agent.py` output | Batch generation (new block) |
| `retrieved_examples_json` | `knowledge_base_retriever.py` output | Batch generation (new block) |
| `style_profile_json` | `alte_vorhabensbeschreibung_style_profile.style_summary_json` | Batch generation |
| `website_text_preview` | Truncated `company.website_clean_text` | Batch generation, chat |

### 5.2 PromptBuilder — `services/prompt_builder.py`

`PromptBuilder` is the single point of prompt assembly. It accepts a `ProjectContext` object (or `None` for backward compatibility) and returns assembled prompt strings. It has no I/O and makes no database calls.

**Context budget (approximate, gpt-4o-mini):**

| Block | Tokens |
|-------|--------|
| System prompt | ~500 |
| Funding rules | ~2,000 |
| Company profile | ~1,000 |
| Website / transcript text | ~6,000 |
| Project topic + domain research | ~2,000 |
| Retrieved examples (max 3) | ~4,000 |
| Style guide | ~1,000 |
| Generation task | ~1,000 |
| **Total** | **~17,500** (well within 128k limit) |

### 5.3 Prompt Block Order (load-bearing — do not change without testing)

```
=== 1. FÖRDERRICHTLINIEN ===         ← funding_rules_json  (primary constraint)
=== 2. FIRMENINFORMATIONEN ===        ← company_profile + website/transcript text
=== 3. PROJEKTTHEMA UND DOMÄNE ===   ← topic + domain_research_json  (NEW in v2)
=== 4. REFERENZBEISPIELE ===          ← retrieved_examples_json  (NEW in v2)
=== 5. STIL-LEITFADEN ===             ← style_profile_json
=== 6. GENERIERUNGSAUFGABE ===        ← section list to generate
```

Rules are injected first so the model treats them as the primary constraint. This order is load-bearing. Changing it changes generation behaviour.

### 5.4 Batch Generation

Located in `documents.py:_generate_batch_content()`. Sections are split into batches of 3–5. Each batch is one LLM call. `milestone_table` sections are always skipped. Output: strict JSON `{ section_id: "text", ... }`. Retries up to 2× on structural failure.

Generation call now:
```
POST /documents/{id}/generate-content
    │
    ├── Load document, resolve project_id
    ├── Load ProjectContext (or fall back to direct assembly if absent)
    ├── PromptBuilder(context).build_generation_prompt(sections)
    └── LLM call (unchanged: gpt-4o-mini, temp=0.7, json_object, timeout=120s)
```

### 5.5 Section Edit

Located in `documents.py:_generate_section_content()`. Called via `POST /documents/{id}/chat` when the message targets a section. Returns a suggestion only — not saved until user approves via `POST /documents/{id}/chat/confirm`. Section titles are never modified by suggestions.

### 5.6 Q&A

Located in `documents.py:_answer_question_with_context()`. Called via `POST /documents/{id}/chat` when the message is a question. Returns a plain text answer. No database write.

### 5.7 Prompt Injection Protection

User-controlled strings (`instruction`, `user_query`) are wrapped with XML delimiters before all prompt injections:

```xml
<user_instruction>
{user_input}
</user_instruction>
```

None guards are applied before wrapping: `instruction_text = instruction or ""`. Do not remove these.

### 5.8 Token Logging

All LLM call sites log prompt size before each API call:

```python
approx_tokens = len(prompt) // 4
logger.info("LLM %s prompt size (chars): %s", step, len(prompt))
logger.info("LLM %s prompt tokens: %s", step, approx_tokens)
```

Never log prompt content, section text, or company data.

---

## 6. Knowledge Base Architecture

### 6.1 Purpose

The knowledge base is infrastructure — not a user-facing feature. It makes the AI produce better first drafts by providing relevant examples from past applications and domain documents. Users never interact with it directly.

### 6.2 Document Categories

| Category | Contents | Retrieval mode |
|----------|----------|---------------|
| `past_application` | Historical Vorhabensbeschreibungen | Semantic (pgvector) |
| `guideline` | Program guidelines, IB documentation | Exact (pre-extracted rules_json) |
| `domain_document` | State programs, reporting instructions, billing documentation | Exact or semantic |
| `style_reference` | Writing style examples | Exact (style_summary_json) |

### 6.3 Data Model

```
knowledge_base_documents
  ├─ id (UUID PK)
  ├─ category: "past_application" | "guideline" | "domain_document" | "style_reference"
  ├─ program_tag: "wtt" | "zim" | null
  ├─ title
  ├─ file_id (FK → files)
  ├─ full_text (extracted)
  └─ processed_at

knowledge_base_chunks  (for semantic retrieval)
  ├─ id (UUID PK)
  ├─ document_id (FK → knowledge_base_documents)
  ├─ section_type: "innovation_approach" | "state_of_art" | "einleitung" | ...
  ├─ chunk_text
  └─ embedding (vector, 1536-dim — text-embedding-3-small)
```

### 6.4 Retrieval

`knowledge_base_retriever.py` embeds a query (project topic + company name) and performs a pgvector cosine similarity search against `knowledge_base_chunks`. Returns top-k chunks as `retrieved_examples_json`, capped at 3 to stay within the context budget.

**pgvector requirement:** The `vector` PostgreSQL extension must be enabled on the production database (`CREATE EXTENSION vector`). No application code change is required for this.

### 6.5 Relationship to Existing `AlteVorhabensbeschreibung`

The `alte_vorhabensbeschreibung_style_profile` system is conceptually a single-category, single-hash knowledge base. It is not migrated into `knowledge_base_documents` — it remains in its own table for backward compatibility. Conceptually it belongs to the `style_reference` category.

---

## 7. Research Agent

### 7.1 Purpose

`services/research_agent.py` enriches project context when company information is insufficient. It performs structured web searches and stores results as `domain_research_json` in `ProjectContext`.

### 7.2 Trigger Conditions

Research is triggered (during Stage 4 of context assembly) only when:
- Company has no `company_profile`  AND
- Company has no `website` and no uploaded documents

It is not triggered on every project creation. It is a fallback, not a default step.

### 7.3 Search Scope

```
Pass 1 — Company context
  Query: "{company_name} Germany industry products technologies"
  Output: structured company enrichment

Pass 2 — Domain / State of the Art
  Query: "{topic} state of the art {year}"
  Output: domain_research_json.state_of_art_summary

Pass 3 — Competitive landscape (brief)
  Query: "{topic} existing solutions"
  Output: domain_research_json.competitive_landscape
```

### 7.4 Security Constraints

- Outbound HTTP requests go to a **fixed, trusted search API endpoint only** (e.g., Brave Search API base URL)
- The search query is user-influenced (company name + topic) but the **request target is never user-controlled**
- All outbound URLs must be validated against RFC 1918 private IP ranges before connection
- Raw search result snippets must not be injected directly into generation prompts — they must pass through the LLM summarisation step first

### 7.5 Cost Controls

- Triggered once per project during initialisation
- Result cached in `ProjectContext`; not re-triggered unless user explicitly requests refresh
- Three targeted queries maximum per project

---

## 8. Database Schema

### 8.1 New Tables (v2)

```
projects
  ├─ id (UUID PK)
  ├─ name (String — e.g., "OKB Sondermaschinenbau × WTT 2025")
  ├─ user_email (FK → users.email)
  ├─ company_id (FK → companies.id)
  ├─ funding_program_id (FK → funding_programs.id)
  ├─ topic (Text — user-entered project topic)
  ├─ status (String — see §4.3)
  ├─ template_resolved (String — system template name or UUID)
  ├─ created_at, updated_at (DateTime tz-aware)

project_contexts
  ├─ id (UUID PK)
  ├─ project_id (FK → projects.id, UNIQUE)
  ├─ company_profile_json (JSON, nullable)
  ├─ funding_rules_json (JSON, nullable)
  ├─ domain_research_json (JSON, nullable)
  ├─ retrieved_examples_json (JSON, nullable)
  ├─ style_profile_json (JSON, nullable)
  ├─ website_text_preview (Text, nullable — truncated)
  ├─ context_hash (Text — combined hash for invalidation)
  ├─ assembled_at (DateTime tz-aware, nullable)

knowledge_base_documents
  ├─ id (UUID PK)
  ├─ category (String)
  ├─ program_tag (String, nullable)
  ├─ title (String)
  ├─ file_id (FK → files.id)
  ├─ full_text (Text)
  ├─ processed_at (DateTime tz-aware, nullable)

knowledge_base_chunks
  ├─ id (UUID PK)
  ├─ document_id (FK → knowledge_base_documents.id)
  ├─ section_type (String)
  ├─ chunk_text (Text)
  └─ embedding (Vector 1536)
```

### 8.2 Document FK Addition

`documents` gains a nullable `project_id` FK to `projects.id` in the v2 migration. Existing documents have `project_id = NULL` and continue to work via the v1 context fallback path.

### 8.3 Unchanged Tables

`users`, `companies`, `funding_programs`, `funding_program_companies`, `company_documents`, `funding_program_documents`, `funding_program_guidelines_summary`, `files`, `user_templates`, `audio_transcript_cache`, `website_text_cache`, `document_text_cache`, `alte_vorhabensbeschreibung_documents`, `alte_vorhabensbeschreibung_style_profile`.

### 8.4 Migration Strategy

All v2 schema changes are additive. No existing columns are modified or removed. New migrations are appended to the Alembic chain. Existing migration files are never modified.

---

## 9. Frontend Architecture

### 9.1 Primary Routes (v2)

| Route | Page | Notes |
|-------|------|-------|
| `/login` | `LoginPage` | Unchanged |
| `/dashboard` | `DashboardPage` | Now shows project list (replaces entity overview) |
| `/projects/new` | `NewProjectPage` | NEW — 3-field creation form |
| `/projects/:id` | `ProjectWorkspacePage` | NEW — central work surface |

### 9.2 Retained Routes (not in primary nav)

| Route | Page | Notes |
|-------|------|-------|
| `/companies` | `CompaniesPage` | Accessible via settings |
| `/funding-programs` | `FundingProgramsPage` | Accessible via settings |
| `/documents` | `DocumentsPage` | Legacy document list |
| `/editor/:companyId/:docType` | `EditorPage` | Accessed from workspace, not direct nav |
| `/templates` | `TemplatesPage` | Accessible via settings |
| `/templates/new` | `TemplateEditorPage` | Accessible via settings |
| `/templates/:id/edit` | `TemplateEditorPage` | Accessible via settings |
| `/alte-vorhabensbeschreibung` | `AlteVorhabensbeschreibungPage` | Admin only |

Do not remove any of these routes. They remain functional.

### 9.3 New Pages

**`NewProjectPage`:** Single form with three required fields (Company, Funding Program, Topic) and one optional expandable section (website, documents, audio). One action: Start Analysis. Navigates to workspace on project creation.

**`ProjectWorkspacePage`:** Fetches project and ProjectContext status on mount. Contains: section sidebar (pre-populated from resolved template), section editor (adapted EditorPage behavior), context panel (shows what the AI knows), AI chat panel. All state is local to this component — no new global state.

### 9.4 Editor State Machine

The existing `EditorPage` state machine is unchanged:
```
reviewHeadings → confirmedHeadings → editingContent
```
In v2, this behaviour is embedded within `ProjectWorkspacePage`. The standalone `/editor/:companyId/:docType` route is retained for backward compatibility.

### 9.5 Unchanged Frontend Rules

- All HTTP calls go through `src/utils/api.ts` — no direct `fetch()` calls
- `ProtectedRoute` wraps all authenticated pages
- `AuthContext` is the only global state — do not add new Contexts or stores
- Handle `AUTH_EXPIRED` explicitly in every component that calls the API
- File upload `FormData` contracts are unchanged

---

## 10. External Services

### 10.1 OpenAI API

Used for all LLM calls and audio transcription. Six existing call sites (see §5). One new call site in `knowledge_base_retriever.py` for embedding generation (`text-embedding-3-small`).

Model usage:

| Use | Model |
|-----|-------|
| All text generation and extraction | `gpt-4o-mini` |
| Audio transcription | `whisper-1` |
| Knowledge base embeddings | `text-embedding-3-small` |

### 10.2 Supabase Storage

Used for all uploaded files. Hash-based deduplication via `file_storage.py`. Unchanged in v2.

### 10.3 PostHog Analytics

Analytics event capture. Graceful failure — never blocks features. Unchanged in v2.

### 10.4 Web Search API (Phase 4, optional)

Used by `research_agent.py`. Provider: Brave Search API or equivalent. Requires one new environment variable (`WEB_SEARCH_API_KEY`). All requests go to the provider's fixed base URL only.

---

## 11. Async Processing

### 11.1 Mechanism

FastAPI `BackgroundTasks` — synchronous Python functions run in Uvicorn's thread pool after the HTTP response is returned to the client.

### 11.2 Existing Background Tasks

`process_company_background()` in `companies.py:166` — unchanged. Creates its own `SessionLocal()`.

### 11.3 New Background Task (v2)

`assemble_project_context()` in `services/context_assembler.py` — triggered on project creation and on context invalidation. Creates its own `SessionLocal()`. Updates `project.status` throughout.

### 11.4 Thread Ceiling Note

Two potentially long-running background tasks now exist concurrently. Audio transcription (Whisper) can take minutes. Context assembly (multi-stage, includes crawl and LLM calls) can also take minutes. At current scale this is acceptable. Under concurrent load, thread exhaustion is a risk.

---

## 12. Template System

### 12.1 Resolution (unchanged)

```
Document has template_id (UUID)?  → user template (ownership verified)
Document has template_name?       → system template by name
Default                           → "wtt_v1"
```

### 12.2 v2 Change: Template Resolved at Project Creation

In v2, the template is resolved once when the project is created and stored as `project.template_resolved`. Documents scoped to the project inherit this value. The user never selects a template manually.

### 12.3 System Templates

Python modules in `backend/app/templates/`. Currently: `wtt_v1` only. Each must be registered in `backend/app/templates/__init__.py`.

---

## 13. What Breaks and Why

| If you do this | What breaks |
|----------------|------------|
| Add a new router prefix without updating the SPA skip list in `main.py` | SPA catch-all silently serves `index.html` for API calls |
| Remove `get_current_user` from any endpoint | Endpoint becomes unauthenticated; ownership checks also fail |
| Remove the `project_id IS NULL` fallback from `documents.py` generation | All pre-v2 documents lose generation capability |
| Call `PromptBuilder` with a `ProjectContext` that is still assembling | Partial context used for generation — warn user before allowing this |
| Change `content_json` section structure | `EditorPage`, all generation functions, and export renderers assume `{id, title, content}` |
| Change `headings_confirmed` from Integer to Boolean | SQLite compatibility breaks — intentionally Integer |
| Change prompt block order in `PromptBuilder` | Generation quality shifts — German output is sensitive to ordering |
| Remove XML delimiters from `instruction` or `user_query` | Re-opens prompt injection vulnerability |
| Set `Base.metadata.create_all()` unconditionally at startup | Conflicts with Alembic-managed schema on PostgreSQL |
| Add knowledge base embeddings without enabling pgvector extension | `knowledge_base_retriever.py` will error on every retrieval query |
| Point `research_agent.py` outbound requests at a user-supplied URL | SSRF vulnerability |
