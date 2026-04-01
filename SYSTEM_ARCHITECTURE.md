# System Architecture — Innovo Claude

> **Audience:** AI agents and engineers making structural changes to this codebase.
> **Scope:** Technical implementation detail. For product purpose, see `PRODUCT_REQUIREMENTS.md`.
> **Version:** v3 — RAG-powered document generation. Canonical backend is `innovo_backend/`.
> **Status:** Verified against source code 2026-04.
> **IMPORTANT:** `/backend/app/` is the legacy monolith. It is read-only reference material.
> All active development goes in `backend/innovo_backend/`. Never add code to `/backend/app/`.

---

## 1. Process Model

The application runs as **a single Uvicorn process** from `backend/innovo_backend/main.py`. There is no separate worker or message broker. Background work runs in-process via FastAPI's `BackgroundTasks`. A separate APScheduler instance handles the monthly re-scrape job.

```
Single Uvicorn Process
├── FastAPI event loop (asyncio)
│   ├── HTTP request handlers (async)
│   ├── BackgroundTasks (sync functions scheduled post-response)
│   └── Lifespan hooks (PostHog init/shutdown, APScheduler start/stop)
├── APScheduler (BackgroundScheduler — monthly funding source re-scrape)
└── SQLAlchemy session pool (sync, threadlocal)
```

**Thread ceiling constraint:** `BackgroundTasks` runs sync functions in Uvicorn's thread pool. Two long-running background tasks exist concurrently: company processing (Whisper transcription, up to minutes) and project context assembly (crawl + extraction chain). Do not add further long-running synchronous background tasks without acknowledging this constraint.

---

## 2. System Overview

### 2.1 What This System Is

Innovo is a **RAG-powered document generation system**. The backend's core job is:

1. Ingest and process multiple sources of knowledge (historical documents, company data, funding rules)
2. Chunk, embed, and store all of it in a vector store (pgvector on PostgreSQL)
3. At generation time, retrieve the most relevant chunks per section and pass them to an LLM
4. Support iterative refinement of generated content via a chat interface that also uses RAG

Everything the LLM generates is grounded in retrieved context. Generation quality depends entirely on ingestion and retrieval quality.

### 2.2 Two Roles, Two Responsibilities

| Role | Responsibility |
|------|---------------|
| **Admin** | Populates the knowledge base — uploads style references, company files, funding guidelines; adds funding program URLs for scraping |
| **User** | Creates projects, monitors context assembly, confirms the template, triggers generation, refines output via chat |

### 2.3 The Central Entity

`Project` is the first-class entity. It binds a `Company`, a `FundingProgram`, and a body of generated work under a single user-defined topic.

```
User
 └─ Project
       ├─ company_id          FK → companies (shared, reusable)
       ├─ funding_program_id  FK → funding_programs (shared, reusable)
       ├─ topic               "Robot automation for weld seam tracking"
       ├─ status              assembling | ready | generating | complete
       └─ ProjectContext       Pre-assembled context snapshot
```

---

## 3. Backend Architecture

### 3.1 Entry Point — `backend/innovo_backend/main.py`

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
10. Register request logging middleware (adds X-Request-ID header)
11. Include all routers
12. Mount /assets static files (frontend build artifacts)
13. Register /health endpoint
14. Start APScheduler (monthly funding source re-scrape job)
15. Register SPA catch-all route (must be last)
```

**SPA catch-all skip list:** The catch-all `GET /{full_path:path}` skips paths starting with known API prefixes. Current list: `auth/`, `funding-programs`, `companies`, `documents`, `templates`, `health`, `assets/`, `projects`, `knowledge-base`, `alte-vorhabensbeschreibung`, `upload-audio`, `user-templates`.

**Critical rule:** Every new router prefix must be added to this skip list. Omitting it causes the SPA to silently serve `index.html` for API calls in production.

### 3.2 Router Layout — `backend/innovo_backend/services/`

All routers are registered on the root FastAPI app (no `/api` prefix).

| Router file | Path prefix | Admin-only mutation | Status |
|-------------|-------------|--------------------|----|
| `services/auth/router.py` | `/auth/*` | — | Active |
| `services/companies/router.py` | `/companies`, `/upload-audio` | — | Active |
| `services/funding_programs/router.py` | `/funding-programs` | POST/PUT/DELETE | Active |
| `services/documents/router.py` | `/documents` | — | Active |
| `services/templates/router.py` | `/templates`, `/user-templates` | — | Active |
| `services/alte_vorhabensbeschreibung/router.py` | `/alte-vorhabensbeschreibung` | — | Active |
| `services/projects/router.py` | `/projects` | — | Active |
| `services/projects/chat_router.py` | `/projects/{id}/chat` | — | Active |
| `services/knowledge_base/router.py` | `/knowledge-base` | All endpoints | Active |

### 3.3 Service Layer — `backend/innovo_backend/services/`

Each service directory owns its router, its business logic, and its relationship to the shared DB. Services never import from each other — they import from `shared/` only.

| Service | Router | Key responsibilities |
|---------|--------|---------------------|
| `services/auth/` | `router.py` | Register, login, JWT issue, password reset |
| `services/companies/` | `router.py` | Company CRUD, website scraping, audio transcription, company profile extraction |
| `services/funding_programs/` | `router.py` | Program CRUD, guideline ingestion (URL + file upload), guidelines summary extraction |
| `services/documents/` | `router.py`, `service.py`, `prompt_builder.py` | Per-section RAG generation, export (DOCX/PDF) |
| `services/templates/` | `router.py`, `registry.py` | System + user template CRUD, template resolution |
| `services/alte_vorhabensbeschreibung/` | `router.py` | Historical doc upload, style profile extraction |
| `services/projects/` | `router.py`, `chat_router.py`, `context_assembler.py`, `chat_service.py` | Project lifecycle, context assembly, chat-based RAG refinement |
| `services/knowledge_base/` | `router.py`, `retriever.py`, `scraper.py` | Admin KB management, embedding, vector retrieval |

**Dependency rule:** Routers call service functions. Service functions call shared modules. Services never call routers. Business logic does not live in routers.

### 3.4 Shared Modules — `backend/innovo_backend/shared/`

These modules are used across all services and imported only from `shared/`.

| Module | Responsibility |
|--------|---------------|
| `models.py` | All SQLAlchemy ORM models — single source of truth for schema |
| `schemas.py` | Shared Pydantic request/response schemas |
| `database.py` | SQLAlchemy session factory (SQLite dev / PostgreSQL prod) |
| `dependencies.py` | `get_current_user` FastAPI dependency (JWT → User) |
| `jwt_utils.py` | Token generation and verification (HS256) |
| `file_storage.py` | Supabase upload, SHA-256 deduplication |
| `document_extraction.py` | Text extraction from PDFs (pdfplumber) and DOCX (python-docx) |
| `text_cleaning.py` | Boilerplate removal, filler word cleanup |
| `extraction.py` | LLM extraction of structured company profile from text |
| `guidelines_processing.py` | LLM extraction of structured rules from guideline text |
| `style_extraction.py` | LLM extraction of writing style patterns from historical docs |
| `processing_cache.py` | Hash-based cache read/write for all three cache tables |
| `template_resolver.py` | Template resolution: user template → system template → default |
| `observability.py` | Request tracking, structured logging, request_id generation |
| `posthog_client.py` | PostHog analytics event capture |
| `funding_program_documents.py` | Shared helpers for funding program document handling |
| `utils.py` | General utility functions |
| `core/config.py` | Settings (pydantic_settings.BaseSettings), env var loading |

### 3.5 Authentication

Every protected endpoint uses the `get_current_user` dependency.

```
Request: Authorization: Bearer <jwt>
    │
    ▼
shared/dependencies.py: get_current_user()
    │
    shared/jwt_utils.py: verify_token()
    │
    ├── Valid   → DB lookup by email → return User
    └── Invalid → HTTP 401
```

JWT parameters: HS256, 24-hour access token, 1-hour password reset token.

### 3.6 Database Layer

Development: SQLite (`backend/innovo.db`, auto-created).
Production: PostgreSQL (Supabase), pool_size=5, max_overflow=10, pool_pre_ping=True, sslmode=require.

Schema management: Alembic only in production. `Base.metadata.create_all()` is suppressed for PostgreSQL.

---

## 4. RAG Ingestion Pipeline

### 4.1 The Universal Pipeline

Every document or data source the admin or user provides goes through the same four-stage pipeline before it can be used in generation:

```
EXTRACT → CHUNK → EMBED → STORE
```

**Stage 1 — EXTRACT**
Raw text is extracted from the source:
- PDF/DOCX files → `shared/document_extraction.py` (pdfplumber, python-docx)
- Audio files → OpenAI Whisper API transcription
- URLs → web scraping (`services/knowledge_base/scraper.py`), handles JS-rendered pages, dropdowns, downloadable linked files

**Stage 2 — CHUNK**
Extracted text is split into overlapping chunks. Chunking rules:
- Never split mid-sentence
- Never split mid-section
- Prepend the parent section heading to each chunk's text (preserves context for retrieval)
- Chunk size and overlap are configurable per document type

**Stage 3 — EMBED**
Each chunk is passed to `text-embedding-3-small` (OpenAI embedding endpoint).
The resulting 1536-dimension vector is stored alongside the chunk text.

> **CRITICAL: Single embedding model rule.**
> The embedding model is `text-embedding-3-small` across every ingestion path in the system.
> Never mix embedding models. If the model changes, every chunk in the database must be
> re-embedded before retrieval will work. Document this model in CLAUDE.md as a constant.

**Stage 4 — STORE**
Each chunk is stored in `knowledge_base_chunks` with:

```
knowledge_base_chunks
  id             UUID primary key
  document_id    FK → knowledge_base_documents
  chunk_text     TEXT
  embedding      vector(1536)
  chunk_index    INTEGER
  source_type    TEXT   ← alte_vorhabensbeschreibung | company_detail |
                            funding_guideline | company_website |
                            user_upload | audio_transcript
  source_id      UUID   ← FK to parent entity (company_id, program_id, project_id)
  metadata       JSONB  ← { page_number, section_heading, chunk_index, language }
```

> **NOTE — Pending schema migration:** The actual `knowledge_base_chunks` model currently has
> only `(document_id, chunk_text, embedding, chunk_index)`. The `source_type`, `source_id`,
> and `metadata` fields are the target schema and require a migration before they can be used.
> Do not write retrieval code that depends on these fields until the migration is applied.

### 4.2 Ingestion Source 1 — Alte Vorhabensbeschreibung

- **Who triggers it:** Admin uploads PDF/DOCX files via `/alte-vorhabensbeschreibung/upload`
- **Category tag:** `alte_vorhabensbeschreibung`
- **Pipeline:** EXTRACT → CHUNK → EMBED → STORE

After storage, an additional LLM call runs to produce a style profile:

```
STYLE PROFILE EXTRACTION (separate LLM call — temperature 0.0)
Analyses the full document text and extracts:
  - Tone: formal level, technical density, passive vs active voice
  - Structure: ordered list of sections found, typical section length
  - Sentence patterns: how problems are introduced, solutions framed
  - Vocabulary: domain-specific terms used
  - Language: DE or EN

Stored in: alte_vorhabensbeschreibung_style_profile (keyed by combined_hash of all docs)
Used in: system prompt of every section generation call to enforce Innovo's house style
```

### 4.3 Ingestion Source 2 — Company Data

**Sub-source A — Company detail files (admin uploads):**
- Category tag: `company_detail`
- Standard file ingestion pipeline (EXTRACT → CHUNK → EMBED → STORE)

**Sub-source B — Company website scrape (triggered at project creation when user provides URL):**
- Category tag: `company_website`
- Scraper crawls main URL plus at least one level deep (about, products, technology pages)
- Extracts all visible text, ignores nav/footer boilerplate
- Stores raw text in `website_text_cache` (keyed by URL hash) — check cache first
- Then: CHUNK → EMBED → STORE with `company_id` as `source_id`

After ingestion, a structured company profile is extracted via LLM:
```
COMPANY PROFILE EXTRACTION (LLM call — temperature 0.0)
Extracts:
  - Company name, industry, core product/service
  - Key technologies used
  - Problem they solve
  - Target market

Stored in: companies.company_profile (JSONB)
Used in: project context assembly Stage 1, generation prompt block 2
```

### 4.4 Ingestion Source 3 — Funding Program Guidelines

Admin can add funding program guidelines via **two paths**:

**Path A — URL scraping:**
- Admin provides a URL via `POST /funding-programs/{id}/guidelines/upload` with a URL field
- Scraper (`services/knowledge_base/scraper.py`) handles:
  - Static HTML pages → extract all text
  - Accordion/dropdown sections → expand and read hidden content
  - Linked PDF/Word files → download, extract text, ingest separately
  - Sub-pages linked from the main URL that are funding-relevant → follow and scrape
- Stores URL in `funding_program_sources` table for monthly re-scrape
- Pipeline: EXTRACT → CHUNK → EMBED → STORE with `source_type: funding_guideline`

**Path B — Direct file upload:**
- Admin uploads PDF/DOCX files via `POST /funding-programs/{id}/guidelines/upload`
- Standard file ingestion pipeline (EXTRACT → CHUNK → EMBED → STORE)

Both paths trigger the same downstream LLM call:
```
GUIDELINES SUMMARY EXTRACTION (LLM call — temperature 0.3)
Extracts structured rules:
  - Eligibility criteria (who can apply)
  - Mandatory document sections (what must be included)
  - Word/page limits per section
  - Formatting requirements
  - Submission deadlines if present
  - Funding amount range if present

Stored in: funding_program_guidelines_summary.rules_json
Used in: context assembly Stage 2, generation system prompt (hard constraints per section)
```

### 4.5 Ingestion Source 4 — User-Provided Context (at Project Creation)

Optional. User provides at project creation time:
- Document uploads → EXTRACT → CHUNK → EMBED → STORE with `source_type: user_upload`, `source_id: project_id`
- Pre-recorded audio file → transcribe via Whisper → CHUNK → EMBED → STORE with `source_type: audio_transcript`, `source_id: project_id`
- Live voice recording → save audio → transcribe → CHUNK → EMBED → STORE

All user-provided context is scoped to the project (`project_id` as `source_id`). It supplements — never replaces — the admin knowledge base.

---

## 5. Project Lifecycle

### 5.1 Creation

```
POST /projects
    │
    ├── Accept: funding_program_id (required), company_name (text, required), topic (required)
    ├── Accept optional: company_id (FK to existing company record), website URL, files, audio
    ├── Resolve template from FundingProgram → store as project.template_overrides_json
    ├── Create Project row (status: "assembling")
    ├── Return project to client immediately
    └── BackgroundTask → assemble_project_context()
```

### 5.2 Context Assembly Pipeline

`context_assembler.py` runs as a background task in five sequential stages. It **always completes with `project.status = "ready"`** regardless of which stages return partial data. Each stage writes its completion status to `assembly_progress_json` so the frontend can display live progress.

```
Stage 1 — Company research
    ├── If company_id set → load company_profile from DB (company_discovery_status: found_in_db)
    ├── If website URL provided → scrape → extract profile (company_discovery_status: scraped_from_url)
    ├── Else → web search by company_name → parse result
    │       → if no result: company_discovery_status: manual (user must provide info)
    └── Write → company_profile to project_contexts
             → assembly_progress_json["company"] = true

Stage 2 — Funding rules
    ├── Load funding_program_guidelines_summary for project.funding_program_id
    ├── Write → guidelines_summary to project_contexts
    └── Write → assembly_progress_json["guidelines"] = true

Stage 3 — Template preparation
    ├── Resolve template (user template → system template → "wtt_v1" default)
    ├── Store resolved template structure
    └── Write → assembly_progress_json["template"] = true

Stage 4 — Knowledge base retrieval (runs in parallel with Stage 3)
    ├── Vector similarity search: query = project.topic + company name
    ├── Filter by: funding_program_id, source_type
    ├── Return top-10 chunks → store as relevant_chunks in project_contexts
    └── (Empty list if KB is empty — not an error)

Stage 5 — Style profile
    ├── Load most recent alte_vorhabensbeschreibung_style_profile
    └── Write → style_profile to project_contexts
             (null if none exists — not an error)

Consolidation (always runs)
    ├── Calculate completeness_score
    └── Set project.status = "ready"  ← unconditional
```

**Partial context is usable.** Missing fields reduce output quality but do not block generation. Chat refinement allows users to add missing information after generation.

### 5.3 Project Status Values

| Status | Set when |
|--------|---------|
| `assembling` | Project row created; context assembly background task is running |
| `ready` | ProjectContext assembled; template preview open; generation available |
| `generating` | Section generation in progress |
| `complete` | Document exported |

`"pending"`, `"failed"`, `"initializing"`, `"context_loading"` are **not valid** lifecycle states. The assembler never sets `"failed"` — it always reaches `"ready"`.

### 5.4 Progress Screen (Frontend)

After project creation, the frontend polls `GET /projects/{id}` every 2 seconds and shows live progress read from `assembly_progress_json`:

```
Step 1 — Extracting company data       [spinner → ✓ when company = true]
Step 2 — Loading funding guidelines    [spinner → ✓ when guidelines = true]
Step 3 — Preparing document template   [spinner → ✓ when template = true]
```

These steps are **informational** — the user watches them complete. No user action is required at Step 1 or Step 2.

Once all three steps show ✓, the template preview opens automatically. The user can then add, remove, rename, and reorder sections. When satisfied, the user clicks **"Confirm template"** — this is the single user action that triggers generation.

### 5.5 Company Discovery Fallback

When `company_discovery_status = "manual"`, the frontend shows:
```
We could not find enough information about [company_name].
Please provide: Website URL, short description, or upload a document.
```

User-provided information is submitted to `PATCH /projects/{id}/context`. The endpoint merges into `company_profile` (does not overwrite) and recalculates `completeness_score`. The full assembler does not re-run.

---

## 6. Document Generation Pipeline

### 6.1 Per-Section RAG Generation

After "Confirm template", each section is generated **independently** via its own RAG retrieval cycle.

**Rationale:** Each section of a Vorhabenbeschreibung requires different context. "Innovation Approach" needs different retrieved chunks than "Problem Statement". Per-section generation means:
- Sharper, more targeted retrieval per section
- A single failed section can be re-triggered without re-running the whole document
- Each section generation is independently idempotent
- Sections can be generated in parallel if needed

**Pipeline per section:**

```
1. RETRIEVE
   Vector similarity search against knowledge_base_chunks:
     Query:  section heading + section description
     Filter: company_id + funding_program_id + project_id
     Top-K:  10 chunks (configurable)

2. BUILD PROMPT
   System prompt:
     ├── Style profile (tone, structure rules from alte Vorhabenbeschreibung)
     └── Funding guidelines constraints for this section (word limits, mandatory content)
   Context:
     ├── Retrieved chunks (top-10)
     └── Company profile JSON
   User prompt:
     ├── Section heading
     └── Any user notes for this section

3. GENERATE
   LLM call (gpt-4o-mini, temperature 0.7, streamed)
   Response streamed to frontend

4. STORE
   Generated text saved to document section record
   Overwrites existing content (idempotent — never appends)
```

**Call site:** `backend/innovo_backend/services/documents/service.py`

### 6.2 Prompt Block Order (load-bearing — do not change without testing)

```
=== 1. FÖRDERRICHTLINIEN ===         ← funding guidelines (primary constraint — always first)
=== 2. FIRMENINFORMATIONEN ===        ← company_profile + website_text_preview
=== 3. REFERENZBEISPIELE ===          ← retrieved chunks for this section
=== 4. STIL-LEITFADEN ===             ← style_profile from alte Vorhabenbeschreibung
=== 5. GENERIERUNGSAUFGABE ===        ← section heading + user notes
```

Rules are injected first so the model treats them as the primary constraint. This order is load-bearing — changing it changes generation behaviour and output quality.

### 6.3 Prompt Injection Protection

All user-controlled strings are wrapped with XML delimiters before injection:

```xml
<user_instruction>
{user_input}
</user_instruction>
```

None guards are applied before wrapping: `instruction_text = instruction or ""`. Do not remove these.

### 6.4 Token Logging

All LLM call sites log prompt size before each API call. Never log prompt content, section text, or company data — metadata only.

```python
approx_tokens = len(prompt) // 4
logger.info("LLM %s prompt size (chars): %s", step, len(prompt))
logger.info("LLM %s prompt tokens (approx): %s", step, approx_tokens)
```

---

## 7. Chat-Based Refinement (RAG)

### 7.1 Pipeline

After generation, the user refines content via a project-scoped chat panel. Each message goes through a 5-step RAG pipeline:

```
Step 1 — PARSE
  Identify which section the user is referencing (e.g. "1.1" → section_id)
  Identify if the message includes attachments (file or audio)

Step 2 — INGEST (only if attachments present)
  Any file or audio attached to a chat message goes through:
    EXTRACT → CHUNK → EMBED → STORE
  scoped to project_id, source_type: user_upload or audio_transcript
  This runs BEFORE retrieval so new content is immediately searchable

Step 3 — RETRIEVE
  Vector similarity search scoped to project_id + referenced section
  Includes newly ingested chunks in the retrieval pool

Step 4 — BUILD PROMPT
  System prompt:
    ├── Style profile
    └── Funding constraints for the referenced section
  Context:
    ├── Retrieved chunks (top-10)
    └── Full chat history for this project (summarised if growing long)
  User message: the chat input

Step 5 — GENERATE + UPDATE
  LLM generates revised section content (streamed)
  If user accepts → section content in DB is overwritten (idempotent)
  If user rejects → no database write
```

**Call site:** `backend/innovo_backend/services/projects/chat_service.py`

### 7.2 Chat History Management

Full chat history is persisted in `project_chat_messages` per project. Context window is managed — older messages are summarised if history grows too long. The summary replaces raw history beyond a configurable message count.

---

## 8. Monthly Background Scraping

### 8.1 APScheduler Job

`innovo_backend/main.py` starts an APScheduler `BackgroundScheduler` at startup.

| Setting | Value |
|---------|-------|
| Schedule | First Monday of every month at 02:00 |
| Job | `scrape_all_sources_task()` |
| Source | All rows in `funding_program_sources` table |

### 8.2 Re-scrape Logic (Idempotent)

For each URL in `funding_program_sources`:
1. Scrape the URL
2. Hash the scraped content
3. Compare to stored `content_hash`
4. **If changed:** delete existing chunks where `source_id = this source_id`, then re-run CHUNK → EMBED → STORE. Update `content_hash` and `last_scraped_at`.
5. **If unchanged:** update `last_scraped_at` only. No re-processing.

This is idempotent — re-running the job on the same content produces the same DB state.

---

## 9. Retrieval Rules

### 9.1 Source Scoping (Hard Rule)

**Every vector similarity search must filter by at least one scope field:**
- `source_id` matching `company_id`
- `source_id` matching `funding_program_id`
- `source_id` matching `project_id`

**Global unfiltered vector search is forbidden.** It returns irrelevant chunks from other companies and projects, degrading generation quality and leaking data.

### 9.2 Cache-First Processing (Hard Rule)

Before scraping a URL: check `website_text_cache` (key: SHA-256 of normalised URL).
Before transcribing audio: check `audio_transcript_cache` (key: file content hash).
Before extracting a document: check `document_text_cache` (key: file content hash).

If cache hit → use cached text, skip processing.
If cache miss or cache older than 30 days (for URL caches) → process and update cache.

**This is a hard rule, not a suggestion.** Re-processing the same content wastes tokens and produces non-deterministic differences in embeddings.

### 9.3 Ingestion Idempotency (Hard Rule)

Re-running ingestion for the same source must not create duplicate chunks.

Protocol: before inserting new chunks for a source, delete all existing chunks where `source_id = this source_id`. Then insert fresh chunks. Never append to existing chunks for the same source.

---

## 10. Knowledge Base Architecture

### 10.1 Purpose

The knowledge base provides relevant examples and context for generation. Users never interact with it directly. Admins manage it via `/knowledge-base/` endpoints.

### 10.2 Document Categories

| Category | Contents | Retrieval mode |
|----------|----------|---------------|
| `alte_vorhabensbeschreibung` | Historical Vorhabensbeschreibungen (style + structure) | Semantic (pgvector) |
| `funding_guideline` | Program guidelines, rules, eligibility | Pre-extracted rules_json + semantic |
| `company_detail` | Admin-uploaded company files | Semantic |
| `company_website` | Scraped company website text | Semantic |
| `user_upload` | Files attached during project creation or chat | Semantic |
| `audio_transcript` | Transcribed audio from project creation or chat | Semantic |

### 10.3 Data Model (Target Schema)

```
knowledge_base_documents
  id           UUID PK
  filename     String
  category     String (see categories above)
  program_tag  String (nullable — e.g. "wtt", "zim")
  file_id      UUID FK → files
  source_id    UUID FK → funding_program_sources (nullable — for URL-scraped docs)
  uploaded_by  String FK → users.email
  created_at   DateTime

knowledge_base_chunks  (target schema — pending migration for source_type/source_id/metadata)
  id           UUID PK
  document_id  UUID FK → knowledge_base_documents
  chunk_text   TEXT
  embedding    vector(1536)   ← text-embedding-3-small
  chunk_index  INTEGER
  source_type  TEXT           ← pending migration
  source_id    UUID           ← pending migration
  metadata     JSONB          ← pending migration
  created_at   DateTime
```

### 10.4 Retrieval

`services/knowledge_base/retriever.py` embeds a query string using `text-embedding-3-small` and performs a pgvector cosine similarity search. Retrieval is always scoped by at least one of: `program_tag`, `source_id`, or `source_type`. Results are capped to top-10 per retrieval call.

**pgvector requirement:** The `vector` PostgreSQL extension must be enabled on the production database (`CREATE EXTENSION vector`). No application code change is required for this.

---

## 11. LLM Call Sites

All LLM calls are in `innovo_backend`. No LLM calls exist in `/backend/app/` (legacy).

| # | Function | File | Purpose | Temp | Max Tokens |
|---|----------|------|---------|------|-----------|
| 1 | `extract_company_profile()` | `shared/extraction.py` | Extract structured facts from website + transcript | 0.0 | unlimited |
| 2 | `generate_style_profile()` | `shared/style_extraction.py` | Extract writing style from historical docs | 0.0 | 2,000 |
| 3 | `extract_rules_from_text()` | `shared/guidelines_processing.py` | Extract structured rules from guideline text | 0.3 | 4,000 |
| 4 | `generate_section_content()` | `services/documents/service.py` | Generate one section via RAG (per-section) | 0.7 | unlimited |
| 5 | `refine_section_via_chat()` | `services/projects/chat_service.py` | Chat-based section refinement | 0.7 | 2,000 |
| 6 | `embed_chunks()` | `services/knowledge_base/retriever.py` | Embed chunks for storage (text-embedding-3-small) | n/a | n/a |
| 7 | `embed_query()` | `services/knowledge_base/retriever.py` | Embed retrieval query at generation time | n/a | n/a |

---

## 12. Database Schema

### 12.1 Project-Centered Entities

```
projects
  id                    UUID PK
  user_email            FK → users.email
  company_id            FK → companies.id (nullable)
  company_name          TEXT  ← used if company_id is null
  funding_program_id    FK → funding_programs.id
  topic                 TEXT
  status                TEXT  ← assembling | ready | generating | complete
  template_overrides_json JSONB (nullable)
  is_archived           BOOLEAN
  created_at / updated_at   DateTime

project_contexts
  project_id                UUID PK, FK → projects.id (UNIQUE)
  company_profile           JSONB    ← structured company data
  guidelines_summary        JSONB    ← extracted funding rules
  style_profile             JSONB    ← matched alte Vorhabenbeschreibung style
  relevant_chunks           JSONB    ← top-K chunks retrieved at assembly time
  assembly_progress_json    JSONB    ← { company: bool, guidelines: bool, template: bool }
  completeness_score        INTEGER  ← 0–100 (not Float)
  company_discovery_status  TEXT     ← found_in_db | scraped_from_url | manual
  website_text_preview      TEXT     ← first 500 chars of scraped company website
  assembled_at              TIMESTAMPTZ

project_chat_messages
  id         UUID PK
  project_id FK → projects.id
  role       TEXT  ← user | assistant
  content    TEXT
  created_at DateTime
```

### 12.2 Knowledge Base Tables

```
funding_program_sources
  id                 UUID PK
  funding_program_id FK → funding_programs.id
  url                TEXT
  label              TEXT (nullable)
  status             TEXT  ← pending | scraping | done | failed
  last_scraped_at    DateTime (nullable)
  content_hash       TEXT (nullable)
  error_message      TEXT (nullable)
  created_at         DateTime

knowledge_base_documents
  id           UUID PK
  filename     TEXT
  category     TEXT
  program_tag  TEXT (nullable)
  file_id      UUID FK → files (nullable)
  source_id    UUID FK → funding_program_sources (nullable)
  uploaded_by  TEXT FK → users.email
  created_at   DateTime

knowledge_base_chunks  (current model — source_type/source_id/metadata pending migration)
  id           UUID PK
  document_id  UUID FK → knowledge_base_documents
  chunk_text   TEXT
  embedding    vector(1536)
  chunk_index  INTEGER
  created_at   DateTime
```

### 12.3 Supporting Entities

`users`, `companies`, `funding_programs`, `funding_program_companies`, `documents`, `files`, `company_documents`, `funding_program_documents`, `funding_program_guidelines_summary`, `user_templates`, `audio_transcript_cache`, `website_text_cache`, `document_text_cache`, `alte_vorhabensbeschreibung_documents`, `alte_vorhabensbeschreibung_style_profile`.

### 12.4 Migration Strategy

All schema changes are additive — no existing columns are modified or removed. New migrations are appended to the Alembic chain. Existing migration files are never modified.

---

## 13. Frontend Architecture

### 13.1 Primary Routes

| Route | Page | Notes |
|-------|------|-------|
| `/login` | `LoginPage` | Public auth entry point |
| `/dashboard` | `DashboardPage` | Project list — primary entry after login |
| `/projects/new` | `NewProjectPage` | Project creation form |
| `/projects/:id` | `ProjectWorkspacePage` | 3-column editor — central work surface |

### 13.2 Admin/Settings Routes

| Route | Page | Notes |
|-------|------|-------|
| `/funding-programs` | `FundingProgramsPage` | Admin: manage programs, upload guidelines |
| `/companies` | `CompaniesPage` | Company management |
| `/admin/knowledge-base` | `KnowledgeBaseAdminPage` | Admin: manage KB documents |
| `/alte-vorhabensbeschreibung` | `AlteVorhabensbeschreibungPage` | Admin: upload style reference docs |
| `/templates` | `TemplatesPage` | Template management |
| `/templates/new`, `/templates/:id/edit` | `TemplateEditorPage` | Create/edit templates |
| `/documents` | `DocumentsPage` | Legacy document list |

### 13.3 Frontend Rules

- All HTTP calls go through `frontend/src/utils/api.ts` — no direct `fetch()` calls anywhere else
- `ProtectedRoute` wraps all authenticated pages
- `AuthContext` is the only global state — do not add new Contexts or stores
- Handle `AUTH_EXPIRED` explicitly in every component that calls the API
- File upload `FormData` contracts must not have `Content-Type` set manually

---

## 14. External Services

| Service | Purpose | Call site |
|---------|---------|-----------|
| OpenAI GPT-4o-mini | All text generation and extraction | `services/documents/service.py`, `services/projects/chat_service.py`, `shared/extraction.py`, `shared/guidelines_processing.py`, `shared/style_extraction.py` |
| OpenAI Whisper-1 | Audio transcription | `services/companies/router.py` (background task) |
| OpenAI text-embedding-3-small | Chunk and query embedding | `services/knowledge_base/retriever.py` |
| Supabase Storage | All uploaded files (hash-deduped) | `shared/file_storage.py` |
| PostHog | Analytics (graceful failure — never blocks) | `shared/posthog_client.py` |

---

## 15. Legacy Note

`/backend/app/` is the original monolith (v1). It is **read-only reference material**.

- Do not add routes, logic, or bug fixes to `/backend/app/`
- Do not extend its models or schemas
- It is kept in the repository only for reference while migration is ongoing
- All active development belongs in `backend/innovo_backend/`

---

## 16. What Breaks and Why

| If you do this | What breaks |
|----------------|------------|
| Add a new router prefix without updating the SPA skip list in `main.py` | SPA serves `index.html` for API calls silently in production |
| Remove `get_current_user` from any endpoint | Endpoint becomes unauthenticated; ownership checks also fail |
| Do a global (unscoped) vector search | Retrieves chunks from unrelated companies/projects; generation quality degrades |
| Mix embedding models across ingestion sources | Cosine similarity becomes meaningless; retrieval returns garbage |
| Change the embedding model without re-embedding all chunks | All retrieval breaks |
| Append new chunks without deleting old chunks for the same source | Duplicate chunks inflate retrieval; idempotency broken |
| Change prompt block order | Generation quality shifts — German output is sensitive to ordering |
| Remove XML delimiters from user inputs | Re-opens prompt injection vulnerability |
| Set `Base.metadata.create_all()` unconditionally at startup | Conflicts with Alembic-managed schema on PostgreSQL |
| Add pgvector queries without enabling the extension | `retriever.py` errors on every query |
| Point scraper outbound requests at a user-supplied URL without RFC 1918 validation | SSRF vulnerability |
| Overwrite rather than merge `company_profile` on PATCH `/projects/{id}/context` | User-provided corrections are lost |
