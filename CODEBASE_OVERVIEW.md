# Codebase Overview — Innovo Claude

> **Architecture:** Project-centered (v2). For full technical detail see `SYSTEM_ARCHITECTURE.md`.
> **Status:** Verified 2026-03.

---

## Backend

**Location:** `backend/`
**Entry point:** `backend/main.py`

### Routers — `backend/app/routers/`

| File | Responsibility | v2 Status |
|------|---------------|-----------|
| `auth.py` | Register, login, password reset | Unchanged |
| `companies.py` | Company CRUD, website crawl, audio upload, background processing | Unchanged |
| `funding_programs.py` | Funding program CRUD, guideline upload and extraction | Unchanged |
| `documents.py` | Document CRUD, generation, chat editing, Q&A, export | Updated: reads from `ProjectContext` via `PromptBuilder` |
| `templates.py` | User template CRUD, system template listing | Unchanged |
| `alte_vorhabensbeschreibung.py` | Style reference doc upload, style profile generation | Unchanged |
| `projects.py` | Project CRUD, status polling, context refresh | **NEW** |
| `knowledge_base.py` | Knowledge base document management (admin-only) | **NEW** |

**Rule:** Every new router prefix must be added to the SPA catch-all skip list in `main.py`.

---

### Services — `backend/app/services/`

New in v2. Contains business logic previously scattered across routers and `documents.py`.

| File | Responsibility |
|------|---------------|
| `context_assembler.py` | Background task: assembles `ProjectContext` from all sources |
| `prompt_builder.py` | Constructs LLM prompts from `ProjectContext`; manages context budget |
| `research_agent.py` | Background task: web research when company data is absent |
| `knowledge_base_retriever.py` | pgvector semantic retrieval from knowledge base chunks |

**Dependency rule:** Routers call services. Services call existing modules. Services never call routers.

---

### Existing Modules — `backend/app/`

Unchanged in v2. Called by services and routers.

| File | Responsibility |
|------|---------------|
| `extraction.py` | LLM extraction of structured company profile from text |
| `preprocessing.py` | Website crawling (BeautifulSoup), audio transcription (Whisper) |
| `guidelines_processing.py` | Structured rule extraction from guideline PDFs |
| `style_extraction.py` | Writing style extraction from historical Vorhabensbeschreibungen |
| `file_storage.py` | Supabase Storage upload, SHA-256 deduplication |
| `document_extraction.py` | Text extraction from PDFs (PyPDF2) and DOCX (python-docx) |
| `text_cleaning.py` | Boilerplate removal, filler word cleanup |
| `processing_cache.py` | Hash-based cache read/write (no TTL) |
| `template_resolver.py` | Template resolution: user template → system template → default |
| `observability.py` | Request tracking, structured logging, request_id generation |
| `posthog_client.py` | PostHog analytics event capture |
| `jwt_utils.py` | JWT generation and verification (HS256) |
| `dependencies.py` | `get_current_user` FastAPI dependency |

---

### Models — `backend/app/models.py`

All SQLAlchemy models. Key entities:

**Existing (unchanged):**
`User`, `Company`, `FundingProgram`, `FundingProgramCompany`, `Document`, `File`, `UserTemplate`, `FundingProgramGuidelinesSummary`, `AlteVorhabensbeschreibungDocument`, `AlteVorhabensbeschreibungStyleProfile`

**Cache tables (unchanged):**
`AudioTranscriptCache`, `WebsiteTextCache`, `DocumentTextCache`

**New in v2:**
`Project`, `ProjectContext`, `KnowledgeBaseDocument`, `KnowledgeBaseChunk`

---

### Templates — `backend/app/templates/`

System templates as Python modules. Currently: `wtt_v1` only.
Each template must be registered in `backend/app/templates/__init__.py`.
In v2, the template is resolved once at project creation and stored as `project.template_resolved`.

---

### Migrations — `backend/alembic/versions/`

18 existing migrations. Do not modify existing migration files.
v2 adds new migrations only (additive — no column changes to existing tables).

---

### Large Files — Handle With Care

| File | Size | Rule |
|------|------|------|
| `backend/app/routers/documents.py` | ~3,300 lines | Read only the relevant function; never load the whole file |

---

## Frontend

**Location:** `frontend/`
**Entry:** `frontend/src/main.tsx`

### Primary Routes (v2 flow)

| Route | Page | Notes |
|-------|------|-------|
| `/login` | `LoginPage` | Public |
| `/dashboard` | `DashboardPage` | Project list — primary entry point |
| `/projects/new` | `NewProjectPage` | **NEW** — creation form |
| `/projects/:id` | `ProjectWorkspacePage` | **NEW** — central work surface |

### Retained Routes (not in primary nav)

| Route | Page | Notes |
|-------|------|-------|
| `/companies` | `CompaniesPage` | Data management (settings) |
| `/funding-programs` | `FundingProgramsPage` | Data management (settings) |
| `/documents` | `DocumentsPage` | Legacy document list |
| `/editor/:companyId/:docType` | `EditorPage` | Accessed from workspace |
| `/templates` | `TemplatesPage` | Template management (settings) |
| `/templates/new` | `TemplateEditorPage` | Create template |
| `/templates/:id/edit` | `TemplateEditorPage` | Edit template |
| `/alte-vorhabensbeschreibung` | `AlteVorhabensbeschreibungPage` | Admin |

Do not remove retained routes — they remain functional.

### Key Files

| File | Purpose | Rule |
|------|---------|------|
| `src/utils/api.ts` | All HTTP calls | Never bypass — no direct `fetch()` calls |
| `src/contexts/AuthContext.tsx` | Auth state | Only global state — do not duplicate |
| `src/components/Layout.tsx` | Nav wrapper for authenticated pages | Updated in v2 for simplified nav |
| `src/components/ProtectedRoute.tsx` | Auth guard | Must wrap all authenticated pages |
| `src/App.tsx` | Route definitions | |

---

## Documentation

| File | Purpose | Audience |
|------|---------|---------|
| `PRODUCT_REQUIREMENTS.md` | Product purpose, detailed workflows, engineering constraints | All |
| `SYSTEM_ARCHITECTURE.md` | Full technical design v2 | Engineers, AI agents |
| `CODEBASE_OVERVIEW.md` | Repository map and quick reference | Engineers, AI agents |
| `CLAUDE.md` | Behavior rules for Claude agents | Claude agents only |
| `AGENTS.md` | Specialized agent responsibilities | Claude agents only |
| `docs/PRODUCT_VISION.md` | Product philosophy and client vision | Product, engineering |
| `docs/AUTHENTICATION_SETUP.md` | Auth operational guide | Engineers |
| `docs/OBSERVABILITY_LOGGING.md` | Logging and monitoring | Engineers |
| `docs/SECURITY_IMPLEMENTATION.md` | Security implementation detail | Engineers |
| `docs/PRODUCTION_READINESS_REVIEW.md` | Pre-deployment checklist | Engineers |
| `docs/QUICK_START.md` | Local development setup | Engineers |

---

## Agent Configuration

`.claude/agents/` — specialized agent instruction files. Select the agent matching your task domain before making changes.

| File | Domain |
|------|--------|
| `backend_agent.md` | Python backend, FastAPI, services, database |
| `llm_pipeline_agent.md` | LLM calls, PromptBuilder, ProjectContext, knowledge base |
| `frontend_agent.md` | React, TypeScript, pages, routing |
| `security_agent.md` | SSRF, prompt injection, auth, data handling |
