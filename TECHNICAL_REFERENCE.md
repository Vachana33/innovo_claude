# Technical Reference

Quick answers to technical questions about this project.

> **IMPORTANT:** The canonical backend is `backend/innovo_backend/`. `/backend/app/` is the
> legacy monolith — read-only reference only. Never add code to `/backend/app/`.

---

## Stack

| Layer | Technology | Version / Notes |
|-------|-----------|----------------|
| Frontend | React + TypeScript + Vite | React 19 |
| Backend | FastAPI + Python | Async, lifespan context |
| ORM | SQLAlchemy | Sync sessions, Alembic migrations |
| Database | PostgreSQL (prod) / SQLite (dev) | SQLite auto-created on startup |
| Auth | JWT HS256 | 24h access tokens, 1h reset tokens |
| AI | OpenAI GPT-4o-mini | Also Whisper-1 (audio), text-embedding-3-small (embeddings) |
| Vector Search | pgvector | Cosine similarity on 1536-dim embeddings |
| File Storage | Supabase Storage | Hash-deduped, bucket: "files" |
| Analytics | PostHog | Silently disabled if key absent |
| Deployment | Render + Docker | See Dockerfile |
| Scheduler | APScheduler | Monthly funding source re-scrape |

---

## Architecture

### Request Path

```
Browser → React (Vite SPA) → innovo_backend router → Service / ORM → PostgreSQL
                                                    ↘ OpenAI API (LLM + Whisper + Embeddings)
                                                    ↘ Supabase Storage
```

### Key Design Decisions

- **No `/api` prefix** — all routes registered at root (`/projects`, `/documents`, etc.)
- **SPA catch-all** — `main.py` serves `index.html` for unmatched routes; must list API prefixes in skip list
- **RAG-powered generation** — every section is generated via its own retrieval cycle (not batch generation)
- **Per-section idempotency** — re-generating a section overwrites existing content, never appends
- **Single embedding model** — `text-embedding-3-small` everywhere; never mix models
- **Scoped vector search** — every pgvector query filters by company_id, funding_program_id, or project_id; global unfiltered search is forbidden
- **Cache-first processing** — website, audio, and document text are cached by hash; never re-process the same content
- **Background tasks** — context assembly and scraping run via FastAPI `BackgroundTask` (not Celery)
- **Monthly APScheduler** — re-scrapes all registered funding source URLs on first Monday of each month at 02:00
- **No push mechanism** — frontend polls `/projects/{id}` every 2s to detect status changes
- **Single global state** — only `AuthContext` in React; all other state is component-local
- **Centralised API client** — all HTTP calls go through `frontend/src/utils/api.ts`

---

## Embedding Model Constant

```
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
```

This model must be used for **every** embed call across the system — chunk ingestion and query embedding at retrieval time. Never change this model without running a full re-embedding migration on all `knowledge_base_chunks` rows. Mixing models breaks cosine similarity.

---

## Database Schema

### `users`
```
email          String PK (lowercase-normalised; domain-restricted)
password_hash  String (bcrypt)
is_admin       Boolean
reset_token_hash     String (nullable)
reset_token_expiry   DateTime (nullable, 1-hour window)
created_at     DateTime
```

### `projects` (v2)
```
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
```

### `project_contexts` (v2) — full schema
```
project_id                UUID PK, FK → projects.id (UNIQUE)
company_profile           JSONB    ← structured company data
guidelines_summary        JSONB    ← extracted funding rules
style_profile             JSONB    ← matched alte Vorhabenbeschreibung style
relevant_chunks           JSONB    ← top-K chunks retrieved at assembly time
assembly_progress_json    JSONB    ← { company: bool, guidelines: bool, template: bool }
completeness_score        INTEGER  ← 0–100 (INTEGER, not Float)
company_discovery_status  TEXT     ← found_in_db | scraped_from_url | manual
website_text_preview      TEXT     ← first 500 chars of scraped company website
assembled_at              TIMESTAMPTZ
```

### `documents`
```
id                  Integer PK
project_id          FK → projects.id (nullable — v1 compat)
company_id          FK → companies.id
funding_program_id  FK → funding_programs.id (nullable)
type                TEXT  ← vorhabensbeschreibung | vorkalkulation
content_json        JSONB  (unvalidated blob: { sections: [...] })
headings_confirmed  INTEGER  ← 0/1, NOT Boolean (SQLite compat)
template_id         UUID FK → user_templates (nullable)
template_name       TEXT (nullable)
title               TEXT (nullable)
updated_at          DateTime
```

### `project_chat_messages` (v2)
```
id          UUID PK
project_id  FK → projects.id
role        TEXT  ← user | assistant
content     TEXT
created_at  DateTime
```

### Cache Tables (keyed by content hash — check before processing)
```
audio_transcript_cache    key: file_content_hash (SHA-256)    value: Whisper transcript
website_text_cache        key: url_hash (SHA-256 of URL)       value: crawled text
document_text_cache       key: file_content_hash (SHA-256)    value: extracted PDF/DOCX text
```

Cache has no TTL for file hashes. URL caches are considered stale after 30 days.

### `knowledge_base_chunks` (current model — pending migration)
```
id           UUID PK
document_id  UUID FK → knowledge_base_documents
chunk_text   TEXT
embedding    vector(1536)   ← text-embedding-3-small
chunk_index  INTEGER
created_at   DateTime
```

> **Pending schema migration:** `source_type` (TEXT), `source_id` (UUID), and `metadata` (JSONB)
> columns need to be added. Do not write retrieval code filtering on these fields until the
> migration is applied. See SYSTEM_ARCHITECTURE.md §4.1 for the target schema.

### `funding_program_sources`
```
id                 UUID PK
funding_program_id FK → funding_programs.id
url                TEXT
label              TEXT (nullable)
status             TEXT  ← pending | scraping | done | failed
last_scraped_at    DateTime (nullable)
content_hash       TEXT (nullable)
error_message      TEXT (nullable)
created_at         DateTime
```

**Critical constraint:** `headings_confirmed` is `Integer`, not `Boolean`. SQLite doesn't have a native bool. Always treat as 0/1.

---

## Auth Flow

```
POST /auth/login
  → bcrypt.verify(password, user.password_hash)
  → jwt.encode({ sub: email, exp: now+24h }, JWT_SECRET_KEY, HS256)
  → return { token, email, is_admin }

Every request:
  → Header: Authorization: Bearer <token>
  → shared/dependencies.py: get_current_user() decodes token
  → Injects user object into route handler

On 401:
  → api.ts clears localStorage token
  → Dispatches AUTH_EXPIRED event
  → App redirects to /login
```

Password reset: separate 1-hour token stored in `users.reset_token_hash`.

---

## RAG Pipeline Summary

```
All ingestion sources go through:
  EXTRACT → CHUNK → EMBED (text-embedding-3-small) → STORE in knowledge_base_chunks

Retrieval at generation time:
  EMBED query → pgvector cosine similarity search (scoped by source_id) → top-10 chunks

Per-section generation:
  RETRIEVE (per section) → BUILD PROMPT → GENERATE (streamed) → STORE (overwrite)

Chat refinement:
  PARSE intent → INGEST attachments (if any) → RETRIEVE → BUILD PROMPT → GENERATE → STORE
```

---

## Context Assembly Pipeline

File: `backend/innovo_backend/services/projects/context_assembler.py`

Runs as a `BackgroundTask` after `POST /projects`. Always terminates with `project.status = "ready"`.

| Stage | Source | Output field | On failure |
|-------|--------|-------------|------------|
| 1. Company | DB profile or web scrape or web search | `company_profile` | `company_discovery_status: manual`, score partial |
| 2. Guidelines | Pre-stored guidelines summary | `guidelines_summary` | Empty JSONB, score 0 |
| 3. Template | Template resolver | `assembly_progress_json["template"]` | Default template used |
| 4. KB retrieval | pgvector search | `relevant_chunks` | Empty list, score 0 |
| 5. Style | Most recent alte_vorhabensbeschreibung_style_profile | `style_profile` | Null, score 0 |

`completeness_score` = sum of weights for stages that returned data (INTEGER 0–100).

---

## LLM Call Sites

All in `backend/innovo_backend/`:

| # | Function | File | Purpose | Model | Temp | Max tokens |
|---|----------|------|---------|-------|------|-----------|
| 1 | `extract_company_profile()` | `shared/extraction.py` | Company facts from website + transcript | gpt-4o-mini | 0.0 | unlimited |
| 2 | `generate_style_profile()` | `shared/style_extraction.py` | Writing patterns from historical docs | gpt-4o-mini | 0.0 | 2,000 |
| 3 | `extract_rules_from_text()` | `shared/guidelines_processing.py` | Rules from guideline text | gpt-4o-mini | 0.3 | 4,000 |
| 4 | `generate_section_content()` | `services/documents/service.py` | Per-section RAG generation | gpt-4o-mini | 0.7 | unlimited |
| 5 | `refine_section_via_chat()` | `services/projects/chat_service.py` | Chat-based section refinement | gpt-4o-mini | 0.7 | 2,000 |
| 6 | `embed_chunks()` | `services/knowledge_base/retriever.py` | Chunk embedding (ingestion) | text-embedding-3-small | n/a | n/a |
| 7 | `embed_query()` | `services/knowledge_base/retriever.py` | Query embedding (retrieval) | text-embedding-3-small | n/a | n/a |

---

## API Endpoints (innovo_backend canonical)

### Auth
```
POST /auth/register
POST /auth/login
POST /auth/request-password-reset
POST /auth/reset-password
```

### Projects (v2)
```
POST   /projects
GET    /projects
GET    /projects/{id}
PUT    /projects/{id}
DELETE /projects/{id}
PATCH  /projects/{id}/context        ← inline merge user-provided data
POST   /projects/{id}/context/refresh ← re-run context assembler
POST   /projects/{id}/generate        ← trigger section generation
GET    /projects/{id}/chat
POST   /projects/{id}/chat
```

### Documents
```
GET    /documents
GET    /documents/by-id/{id}
GET    /documents/{company_id}/vorhabensbeschreibung
DELETE /documents/{id}
PUT    /documents/{id}
POST   /documents/{id}/generate-content
```

### Companies
```
POST   /companies
GET    /companies
GET    /companies/{id}
PUT    /companies/{id}
DELETE /companies/{id}
POST   /upload-audio
POST   /companies/{id}/documents/upload
GET    /companies/{id}/documents
DELETE /companies/{id}/documents/{doc_id}
POST   /companies/{company_id}              ← import company to funding program
```

### Funding Programs
```
POST   /funding-programs              (admin only)
GET    /funding-programs
PUT    /funding-programs/{id}         (admin only)
DELETE /funding-programs/{id}         (admin only)
POST   /funding-programs/{id}/guidelines/upload   ← URL or file
GET    /funding-programs/{id}/documents
DELETE /funding-programs/{id}/documents/{doc_id}
```

### Templates
```
GET    /templates
GET    /templates/system/{name}
GET    /templates/list
POST   /user-templates
GET    /user-templates
GET    /user-templates/{id}
PUT    /user-templates/{id}
POST   /user-templates/duplicate/{id}
DELETE /user-templates/{id}
```

### Knowledge Base (admin only)
```
POST   /knowledge-base/documents
GET    /knowledge-base/documents
DELETE /knowledge-base/documents/{id}
POST   /knowledge-base/funding-sources
GET    /knowledge-base/funding-sources
DELETE /knowledge-base/funding-sources/{id}
POST   /knowledge-base/funding-sources/{id}/refresh
```

---

## Monthly Background Scraping

```
Scheduler: APScheduler BackgroundScheduler (started in innovo_backend/main.py lifespan)
Schedule:  First Monday of every month, 02:00
Job:       scrape_all_sources_task()
Source:    All rows in funding_program_sources

Per URL:
  1. Scrape URL
  2. Hash content
  3. Compare to stored content_hash
  4. If changed  → delete old chunks for source_id, re-run CHUNK → EMBED → STORE
  5. If unchanged → update last_scraped_at only
```

---

## File Upload & Storage

```
1. File received as UploadFile in FastAPI
2. Content hashed (SHA-256) → check files table for existing hash
3. If duplicate → return existing storage_path, skip upload
4. If new → upload to Supabase Storage → save row in files table
5. Processing (transcription / text extraction) also hash-cached
```

Cache tables prevent re-processing the same file content even if re-uploaded.

---

## Frontend Routing

```typescript
/login                        → LoginPage              (public)
/dashboard                    → DashboardPage           (protected)
/projects/new                 → NewProjectPage          (protected)
/projects/:id                 → ProjectWorkspacePage    (protected)
/companies                    → CompaniesPage           (protected)
/funding-programs             → FundingProgramsPage     (protected)
/admin/knowledge-base         → KnowledgeBaseAdminPage  (protected, admin)
/documents                    → DocumentsPage           (protected)
/editor/:companyId/:docType   → EditorPage              (protected, legacy)
/templates                    → TemplatesPage           (protected)
/templates/new                → TemplateEditorPage      (protected)
/alte-vorhabensbeschreibung   → AlteVorhabensbeschreibungPage (protected, admin)
```

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `JWT_SECRET_KEY` | **YES** (RuntimeError if absent) | JWT signing |
| `OPENAI_API_KEY` | Functional | GPT-4o-mini + Whisper + text-embedding-3-small |
| `DATABASE_URL` | No (SQLite fallback) | PostgreSQL connection string |
| `FRONTEND_ORIGIN` | No | CORS allowed origin |
| `SUPABASE_URL` | No | Supabase project URL |
| `SUPABASE_KEY` | No | Supabase service-role key |
| `SUPABASE_STORAGE_BUCKET` | No (default: `"files"`) | Storage bucket name |
| `UPLOAD_DIR` | No | Local audio upload dir (dev) |
| `POSTHOG_API_KEY` | No | Analytics |
| `POSTHOG_DISABLED` | No | Set `"true"` to disable analytics |
| `VITE_API_URL` | No (frontend) | Backend base URL |

---

## Key File Locations (innovo_backend canonical)

| What | Where |
|------|-------|
| App entry point | `backend/innovo_backend/main.py` |
| DB models | `backend/innovo_backend/shared/models.py` |
| Pydantic schemas | `backend/innovo_backend/shared/schemas.py` |
| DB session setup | `backend/innovo_backend/shared/database.py` |
| JWT logic | `backend/innovo_backend/shared/jwt_utils.py` |
| Auth dependency | `backend/innovo_backend/shared/dependencies.py` |
| Config / settings | `backend/innovo_backend/shared/core/config.py` |
| Company profile extraction | `backend/innovo_backend/shared/extraction.py` |
| Style extraction | `backend/innovo_backend/shared/style_extraction.py` |
| Guidelines processing | `backend/innovo_backend/shared/guidelines_processing.py` |
| File storage | `backend/innovo_backend/shared/file_storage.py` |
| Processing caches | `backend/innovo_backend/shared/processing_cache.py` |
| Context assembly | `backend/innovo_backend/services/projects/context_assembler.py` |
| Project chat | `backend/innovo_backend/services/projects/chat_service.py` |
| Section generation | `backend/innovo_backend/services/documents/service.py` |
| Chunk embedding + retrieval | `backend/innovo_backend/services/knowledge_base/retriever.py` |
| URL scraping | `backend/innovo_backend/services/knowledge_base/scraper.py` |
| API client (frontend) | `frontend/src/utils/api.ts` |
| Auth state (frontend) | `frontend/src/contexts/AuthContext.tsx` |
| Project workspace | `frontend/src/pages/ProjectWorkspacePage/` |
| DB migrations | `backend/alembic/versions/` |

---

## Known Technical Debt

| Issue | Location | Risk |
|-------|----------|------|
| `knowledge_base_chunks` missing `source_type`, `source_id`, `metadata` | `shared/models.py` | Blocks scoped retrieval per source type |
| Missing export endpoints in innovo_backend | `services/documents/router.py` | `GET /documents/{id}/export` not yet ported from legacy |
| Missing `GET /projects/{id}/document` endpoint | `services/projects/router.py` | Frontend calls this; returns 404 |
| No rate limiting on auth or LLM endpoints | auth router, documents service | Abuse vector |
| SSRF: user URLs fetched without RFC 1918 validation | `services/knowledge_base/scraper.py` | Security |
| Frontend polls every 2s — no backoff, no push | `ProjectWorkspacePage` | Inefficient under load |
| Password reset token returned in response body (dev path) | `services/auth/router.py` | Remove before production |
| pgvector examples retrieval may be a stub | `services/projects/context_assembler.py` | Feature gap |
