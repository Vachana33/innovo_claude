# Codebase Overview — Innovo Claude

> **Architecture:** RAG-powered document generation system. Project-centered (v2).
> **Canonical backend:** `backend/innovo_backend/` — all new code goes here.
> **Legacy:** `/backend/app/` — read-only reference, do not modify.
> **Status:** Verified 2026-04.

---

## Backend

**Location:** `backend/`
**Entry point:** `backend/innovo_backend/main.py`

---

### innovo_backend/ — Canonical Structure

```
backend/innovo_backend/
├── main.py                          ← FastAPI app, router registration, APScheduler, lifespan
├── __init__.py
├── shared/                          ← Modules imported by all services (no cross-service imports)
│   ├── models.py                    ← All SQLAlchemy ORM models (single source of truth)
│   ├── schemas.py                   ← Shared Pydantic request/response schemas
│   ├── database.py                  ← Session factory (SQLite dev / PostgreSQL prod)
│   ├── dependencies.py              ← get_current_user FastAPI dependency (JWT → User)
│   ├── jwt_utils.py                 ← JWT generation and verification (HS256)
│   ├── file_storage.py              ← Supabase Storage upload, SHA-256 deduplication
│   ├── document_extraction.py       ← Text extraction from PDFs (pdfplumber) and DOCX
│   ├── text_cleaning.py             ← Boilerplate removal, filler word cleanup
│   ├── extraction.py                ← LLM call: extract structured company profile from text
│   ├── guidelines_processing.py     ← LLM call: extract structured rules from guideline text
│   ├── style_extraction.py          ← LLM call: extract writing style from historical docs
│   ├── processing_cache.py          ← Hash-based cache read/write (no TTL for files)
│   ├── template_resolver.py         ← Resolve template: user → system → default "wtt_v1"
│   ├── funding_program_documents.py ← Shared helpers for funding program file handling
│   ├── observability.py             ← Request tracking, structured logging, request_id
│   ├── posthog_client.py            ← PostHog analytics event capture
│   ├── utils.py                     ← General utility functions
│   └── core/
│       ├── config.py                ← Settings (pydantic_settings.BaseSettings), env loading
│       └── __init__.py
└── services/                        ← One directory per domain service
    ├── auth/
    │   ├── router.py                ← Register, login, password reset (4 endpoints)
    │   └── __init__.py
    ├── companies/
    │   ├── router.py                ← Company CRUD, audio upload, website scrape (12 endpoints)
    │   └── __init__.py
    ├── funding_programs/
    │   ├── router.py                ← Program CRUD, guideline ingestion URL+file (7 endpoints)
    │   └── __init__.py
    ├── documents/
    │   ├── router.py                ← Document CRUD, per-section generation (6 endpoints)
    │   ├── service.py               ← Per-section RAG generation logic, export
    │   ├── prompt_builder.py        ← Assembles generation prompts from ProjectContext
    │   └── __init__.py
    ├── templates/
    │   ├── router.py                ← System + user template CRUD (9 endpoints)
    │   ├── registry.py              ← System template registry
    │   ├── wtt_v1.py                ← WTT system template definition
    │   └── __init__.py
    ├── alte_vorhabensbeschreibung/
    │   ├── router.py                ← Style reference doc upload + style profile (6 endpoints)
    │   └── __init__.py
    ├── projects/
    │   ├── router.py                ← Project CRUD, generate, context refresh (8 endpoints)
    │   ├── chat_router.py           ← Project-scoped chat GET/POST (2 endpoints)
    │   ├── context_assembler.py     ← Background task: 5-stage context assembly
    │   ├── chat_service.py          ← 5-step RAG chat pipeline
    │   └── __init__.py
    └── knowledge_base/
        ├── router.py                ← Admin KB management, funding sources (7 endpoints)
        ├── retriever.py             ← pgvector cosine similarity search + embedding calls
        ├── scraper.py               ← URL scraping (static, JS-rendered, downloadable files)
        └── __init__.py
```

---

### RAG Pipeline Modules

The following shared modules and service files together implement the Extract → Chunk → Embed → Store pipeline:

| Stage | Module |
|-------|--------|
| EXTRACT (PDF/DOCX) | `shared/document_extraction.py` |
| EXTRACT (audio) | Whisper API call in `services/companies/router.py` |
| EXTRACT (URL) | `services/knowledge_base/scraper.py` |
| CLEAN text | `shared/text_cleaning.py` |
| CHUNK + EMBED + STORE | `services/knowledge_base/retriever.py` |
| CACHE check/write | `shared/processing_cache.py` |
| RETRIEVE at generation | `services/knowledge_base/retriever.py` |

**Embedding model:** `text-embedding-3-small` (1536 dimensions) — used for every embed call. Never change without a full re-embedding migration.

---

### Service → Table Ownership

| Service | Owns / Writes |
|---------|--------------|
| `services/auth/` | `users` |
| `services/companies/` | `companies`, `company_documents`, `website_text_cache`, `audio_transcript_cache` |
| `services/funding_programs/` | `funding_programs`, `funding_program_documents`, `funding_program_guidelines_summary`, `funding_program_sources` |
| `services/alte_vorhabensbeschreibung/` | `alte_vorhabensbeschreibung_documents`, `alte_vorhabensbeschreibung_style_profile` |
| `services/knowledge_base/` | `knowledge_base_documents`, `knowledge_base_chunks`, `funding_program_sources` (re-scrape) |
| `services/projects/` | `projects`, `project_contexts`, `project_chat_messages` |
| `services/documents/` | `documents`, `document_text_cache` |
| `services/templates/` | `user_templates` |
| `shared/file_storage.py` | `files` (shared registry — used by all services that upload files) |

---

### Routers — All Active (innovo_backend)

| File | Prefix | Endpoints | Admin-only |
|------|--------|-----------|-----------|
| `services/auth/router.py` | `/auth` | 4 | — |
| `services/companies/router.py` | `/companies`, `/upload-audio` | 12 | — |
| `services/funding_programs/router.py` | `/funding-programs` | 7 | POST/PUT/DELETE |
| `services/documents/router.py` | `/documents` | 6 | — |
| `services/templates/router.py` | `/templates`, `/user-templates` | 9 | — |
| `services/alte_vorhabensbeschreibung/router.py` | `/alte-vorhabensbeschreibung` | 6 | — |
| `services/projects/router.py` | `/projects` | 8 | — |
| `services/projects/chat_router.py` | `/projects/{id}/chat` | 2 | — |
| `services/knowledge_base/router.py` | `/knowledge-base` | 7 | All |

---

### Migrations — `backend/alembic/versions/`

Alembic manages the schema in production. `Base.metadata.create_all()` only runs for SQLite (development). Never modify existing migration files. v2 schema changes are additive only.

---

## Frontend

**Location:** `frontend/`
**Entry:** `frontend/src/main.tsx`

### src/ Structure

```
frontend/src/
├── main.tsx                         ← React entry point
├── App.tsx                          ← Route definitions
├── utils/
│   └── api.ts                       ← ALL HTTP calls go through here (no raw fetch() elsewhere)
├── contexts/
│   └── AuthContext.tsx              ← Only global state in the app
├── components/
│   ├── ProtectedRoute.tsx           ← Auth guard — wraps all authenticated pages
│   ├── Layout/                      ← Standard layout for admin/settings pages
│   ├── ProjectShell/                ← 3-column shell for project workspace
│   ├── CreateProjectModal/          ← "+ Create project" modal
│   └── MilestoneTable.tsx           ← Milestone section table component
└── pages/
    ├── LoginPage/
    ├── DashboardPage/               ← Project list (primary entry after login)
    ├── NewProjectPage/              ← Project creation form
    ├── ProjectWorkspacePage/        ← 3-column editor (TOC / content / chat)
    ├── FundingProgramsPage/         ← Admin: manage funding programs
    ├── CompaniesPage/               ← Company data management
    ├── KnowledgeBaseAdminPage/      ← Admin: knowledge base management
    ├── DocumentsPage/               ← Legacy document list
    ├── EditorPage/                  ← Legacy document editor
    ├── TemplatesPage/               ← Template browser
    ├── TemplateEditorPage/          ← Create/edit templates
    └── AlteVorhabensbeschreibungPage/ ← Admin: style reference docs
```

### Primary Routes (v2 user flow)

| Route | Page | Notes |
|-------|------|-------|
| `/login` | `LoginPage` | Public |
| `/dashboard` | `DashboardPage` | Project list — primary entry |
| `/projects/new` | `NewProjectPage` | NEW — creation form |
| `/projects/:id` | `ProjectWorkspacePage` | NEW — central work surface |

### Admin / Settings Routes

| Route | Page | Notes |
|-------|------|-------|
| `/funding-programs` | `FundingProgramsPage` | Admin |
| `/companies` | `CompaniesPage` | Data management |
| `/admin/knowledge-base` | `KnowledgeBaseAdminPage` | Admin |
| `/alte-vorhabensbeschreibung` | `AlteVorhabensbeschreibungPage` | Admin |
| `/templates`, `/templates/new`, `/templates/:id/edit` | Template pages | Settings |
| `/documents` | `DocumentsPage` | Legacy list |
| `/editor/:companyId/:docType` | `EditorPage` | Legacy editor |

Do not remove any of these routes — they remain functional.

### Key Frontend Rules

| File | Rule |
|------|------|
| `src/utils/api.ts` | All HTTP calls must go through here — no direct `fetch()` anywhere |
| `src/contexts/AuthContext.tsx` | Only global state — do not add new Contexts or stores |
| `src/components/ProtectedRoute.tsx` | Must wrap all authenticated pages |

---

## Documentation

| File | Purpose | Audience |
|------|---------|---------|
| `PRODUCT_REQUIREMENTS.md` | Product purpose, detailed workflows, engineering constraints | All |
| `SYSTEM_ARCHITECTURE.md` | Full RAG pipeline, service architecture, data flow | Engineers, AI agents |
| `CODEBASE_OVERVIEW.md` | Repository map, file tree, quick reference | Engineers, AI agents |
| `CLAUDE.md` | Behavior rules and constants for Claude agents | Claude agents only |
| `AGENTS.md` | Specialized agent responsibilities | Claude agents only |
| `TECHNICAL_REFERENCE.md` | Stack, schema, endpoints, LLM call sites, key file locations | Engineers, AI agents |
| `DEVELOPMENT_RULES.md` | Engineering discipline and coding rules | Engineers, AI agents |
| `HOW_IT_ALL_WORKS.md` | Non-technical plain-language explanation | Non-engineers |
| `docs/AUTHENTICATION_SETUP.md` | Auth operational guide | Engineers |
| `docs/OBSERVABILITY_LOGGING.md` | Logging and monitoring | Engineers |
| `docs/SECURITY_IMPLEMENTATION.md` | Security implementation detail | Engineers |
| `docs/QUICK_START.md` | Local development setup | Engineers |

---

## Agent Configuration

`.claude/agents/` — specialized agent instruction files. Select the agent matching your task domain before making changes.

| File | Domain |
|------|--------|
| `backend_agent.md` | Python backend, FastAPI, services, database |
| `llm_pipeline_agent.md` | LLM calls, RAG pipeline, PromptBuilder, ProjectContext, embeddings, retrieval |
| `frontend_agent.md` | React, TypeScript, pages, routing |
| `security_agent.md` | SSRF, prompt injection, auth, data handling |

---

## Large Files — Handle With Care

| File | Size note | Rule |
|------|-----------|------|
| `backend/app/routers/documents.py` | ~3,300 lines | **Legacy only — do not modify.** Read only the relevant function if referencing for context. |
| `backend/innovo_backend/shared/models.py` | All 20+ models | Read specific model only — do not load the whole file |

---

## Legacy — /backend/app/ (Read-Only)

`/backend/app/` is the original monolith. It is **read-only reference material**.

- Do not add routes, logic, or bug fixes to any file under `/backend/app/`
- It is kept for reference while migration is ongoing
- If a feature exists in `/backend/app/` but not in `innovo_backend/`, port the relevant logic cleanly — do not copy-paste

---

## Test Coverage

| Service | Tests present |
|---------|--------------|
| `services/auth/` | Partial (backend/tests/) |
| `services/companies/` | Partial |
| `services/projects/` | Minimal |
| `services/knowledge_base/` | Minimal |
| All others | None confirmed |
| Frontend | No test files found |

Test coverage is low. Do not assume untested code works correctly. When porting features from legacy to `innovo_backend`, add basic smoke tests.
