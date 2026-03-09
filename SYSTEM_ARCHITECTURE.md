# System Architecture — Innovo Claude

> **Audience:** AI agents and engineers making structural changes to this codebase.
> **Scope:** Technical implementation detail. For product purpose and workflows, see `PRODUCT_REQUIREMENTS.md`.
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

**Critical implication:** `BackgroundTasks` runs the background function in the same process as the web server. A long-running background task (audio transcription can take minutes) blocks a thread from the Uvicorn thread pool. This is acceptable at current scale but is a bottleneck under concurrent load. See §6 for details.

---

## 2. Backend Architecture

### 2.1 Entry Point — `backend/main.py`

Startup sequence (order matters):

```
1. Load .env (only if file exists — dev guard)
2. Validate JWT_SECRET_KEY (RuntimeError if absent — hard fail)
3. Warn if OPENAI_API_KEY absent (soft fail — features degrade)
4. Parse DATABASE_URL, detect SQLite vs PostgreSQL
5. If SQLite: run Base.metadata.create_all() (dev convenience)
6. If PostgreSQL: skip create_all() (Alembic migrations own the schema)
7. Instantiate FastAPI app with lifespan context manager
8. Register CORSMiddleware
9. Register three exception handlers (HTTP, Validation, general Exception)
   — all manually set CORS headers to survive middleware ordering issues
10. Include all six routers
11. Mount /assets static files (if backend/static/ exists)
12. Register /health endpoint
13. Register SPA catch-all route (must be last)
```

**CORS origin selection:**
- `FRONTEND_ORIGIN` set → production mode: single origin
- `FRONTEND_ORIGIN` unset → development mode: `localhost:3000`, `localhost:5173`, `localhost:5174`, `127.0.0.1:5173`, `127.0.0.1:5174`
- `allow_methods=["*"]`, `allow_headers=["*"]` (permissive; appropriate for a private internal tool)

**SPA routing:**
The catch-all route `GET /{full_path:path}` serves `backend/static/index.html` for any non-API path. It explicitly skips paths starting with `auth/`, `funding-programs`, `companies`, `documents`, `templates`, `health`, `assets/` to avoid intercepting API routes. **If a new router prefix is added, it must be added to this skip list.**

### 2.2 Router Layout

All routers are registered on the root FastAPI app (no `/api` prefix). Route prefixes are implicit in each router's decorators.

| Router file | URL prefix examples | Key verbs |
|-------------|--------------------|-----------|
| `routers/auth.py` | `/auth/register`, `/auth/login`, `/auth/password-reset-request`, `/auth/password-reset` | POST |
| `routers/companies.py` | `/companies`, `/companies/{id}`, `/upload-audio`, `/companies/{id}/documents` | GET POST PUT DELETE |
| `routers/funding_programs.py` | `/funding-programs`, `/funding-programs/{id}`, `/funding-programs/{id}/guidelines` | GET POST PUT DELETE |
| `routers/documents.py` | `/documents/{company_id}/{type}`, `/documents/{id}/confirm-headings`, `/documents/{id}/generate-content`, `/documents/{id}/chat`, `/documents/{id}/chat/confirm`, `/documents/{id}/export` | GET POST PUT DELETE |
| `routers/templates.py` | `/templates`, `/templates/{id}`, `/system-templates` | GET POST PUT DELETE |
| `routers/alte_vorhabensbeschreibung.py` | `/alte-vorhabensbeschreibung`, `/alte-vorhabensbeschreibung/{id}`, `/alte-vorhabensbeschreibung/style-profile/generate` | GET POST PUT DELETE |

**Special endpoint:**
- `GET /health` — returns `{"status": "ok"}`. Used by Render for health checks. Registered before the SPA catch-all.

### 2.3 Authentication

**Every protected endpoint uses the `get_current_user` dependency** (`backend/app/dependencies.py`).

```python
# Applied via:
current_user: User = Depends(get_current_user)
```

Flow:
```
Request arrives with:  Authorization: Bearer <jwt>
                              │
                              ▼
              dependencies.py: get_current_user()
                              │
                    jwt_utils.py: verify_token()
                              │
                    ┌─────────┴──────────┐
                  Valid                Invalid / Expired
                    │                        │
              DB lookup by email        HTTP 401
                    │
              return User object
```

**JWT parameters** (`backend/app/jwt_utils.py`):
- Algorithm: `HS256`
- Access token expiry: 24 hours
- Password reset token expiry: 1 hour
- Reset tokens include `type: "password_reset"` claim to distinguish them
- Reset tokens stored in DB as SHA-256 hash (one-way), invalidated after use

**Password hashing:** `passlib[bcrypt]` with automatic salt. Comparison is constant-time.

### 2.4 Database Layer

**Connection configuration** (`backend/app/database.py`):

| Environment | URL pattern | Engine config |
|-------------|-------------|---------------|
| Development | `sqlite:///./innovo.db` | `check_same_thread=False` |
| Production | `postgresql://...` or `postgres://...` | pool_size=5, max_overflow=10, pool_pre_ping=True, sslmode=require |

`pool_pre_ping=True` executes a lightweight `SELECT 1` before each connection use, preventing stale-connection errors after database restarts.

**Session lifecycle:**
```python
def get_db():
    db = SessionLocal()
    try:
        yield db          # injected into route handler
    finally:
        db.close()        # always closed, even on exception
```

`autocommit=False`, `autoflush=False` — all writes require explicit `db.commit()`.

**Schema management:**
- Development (SQLite): `Base.metadata.create_all()` runs at startup
- Production (PostgreSQL): Alembic only. `create_all()` is explicitly suppressed.
- Migration files: `backend/alembic/versions/` (18 files)
- Run migrations: `alembic upgrade head` (must be done manually or in deployment pipeline)

### 2.5 Dependency Injection Chain

```
Route handler
    ├── db: Session = Depends(get_db)           # database session
    └── current_user: User = Depends(get_current_user)
                                │
                                └── credentials = Depends(HTTPBearer())
                                └── db: Session = Depends(get_db)
```

Note: `get_db` is called independently for `get_current_user` and for the route handler — each call gets the same session within a single request because FastAPI caches dependency results within a request scope.

---

## 3. Frontend Architecture

### 3.1 Module Structure

```
frontend/src/
├── main.tsx                  # App entry: StrictMode + BrowserRouter + AuthProvider
├── App.tsx                   # Route definitions + ProtectedRoute guards
├── contexts/
│   └── AuthContext.tsx        # Global auth state (isAuthenticated, login, logout)
├── utils/
│   ├── api.ts                 # ALL HTTP calls go through here
│   ├── authUtils.ts           # JWT payload decode (no verification), token helpers
│   └── debugLog.ts            # Conditional dev logging
├── components/
│   ├── Layout.tsx             # Nav wrapper for authenticated pages
│   ├── ProtectedRoute.tsx     # Auth guard — redirects to /login if not authenticated
│   └── MilestoneTable.tsx     # Milestone section component
├── pages/                     # One folder per route
│   ├── LoginPage/
│   ├── DashboardPage/
│   ├── CompaniesPage/
│   ├── FundingProgramsPage/
│   ├── DocumentsPage/
│   ├── EditorPage/            # Core editor — largest page component
│   ├── TemplatesPage/
│   ├── TemplateEditorPage/
│   ├── ProjectPage/
│   └── AlteVorhabensbeschreibungPage/
└── assets/                    # Static images
```

### 3.2 Auth State

`AuthContext` stores: `token`, `userEmail`, `isAuthenticated`.

Token lifecycle:
```
login(token, email?)
  └── stores token in localStorage["innovo_auth_token"]
  └── stores email in localStorage["innovo_user_email"]
  └── sets isAuthenticated = true

logout()
  └── clears both localStorage keys
  └── sets isAuthenticated = false

On page load:
  AuthContext initialises from localStorage
  (no token validation — backend validates on first API call)
```

`authUtils.ts:decodeJWT()` splits the JWT on `.`, base64-decodes the payload, and extracts the `email` or `sub` claim. **No signature verification occurs on the frontend** — this is intentional. Verification is the backend's responsibility.

### 3.3 API Utility — `src/utils/api.ts`

All HTTP calls route through `apiRequest<T>()`. It:
1. Reads `VITE_API_URL` from env (defaults to `http://localhost:8000`)
2. Injects `Authorization: Bearer <token>` if a token exists
3. Sets `Content-Type: application/json` for non-FormData requests
4. On 401: clears tokens and returns `{ error: "AUTH_EXPIRED" }` — **does not redirect**
5. On 204: returns `null`
6. On other errors: extracts `detail` or `message` from JSON response body

File upload functions (`apiUploadFile`, `apiUploadFiles`, `apiUploadFilePut`) use `FormData` and deliberately **omit `Content-Type`** so the browser sets the correct multipart boundary automatically.

**Rule:** Do not make `fetch()` calls outside `api.ts`. Do not hardcode `http://localhost:8000`.

### 3.4 Editor Page State Machine

`EditorPage` manages three mutually exclusive modes:

```
reviewHeadings
    │  POST /documents/{id}/confirm-headings
    ▼
confirmedHeadings
    │  POST /documents/{id}/generate-content
    ▼
editingContent
```

Mode is derived on load from:
- `document.headings_confirmed === 0` → `reviewHeadings`
- `document.headings_confirmed === 1` AND sections have empty content → `confirmedHeadings`
- `document.headings_confirmed === 1` AND sections have content → `editingContent`

**Auto-save:** 1-second debounce on section content changes. Calls `PUT /documents/{id}`. Skipped on initial load and during chat updates (controlled by `isUpdatingFromChat` flag).

**Undo/redo:** Client-side history stacks (`historyPast[]`, `historyFuture[]`). State is snapshotted every 500ms. Duplicate consecutive states are suppressed.

**Status polling:** When `company.processing_status` is not `"done"` or `"failed"`, the editor polls `GET /companies/{id}` every 2000ms. Polling is stopped when a terminal status is reached or the component unmounts.

---

## 4. Document Generation Pipeline

### 4.1 Pipeline Inputs

Before any generation call, three independently-sourced context objects are assembled:

| Input | Source table | Cache key | LLM call that produced it |
|-------|-------------|-----------|--------------------------|
| `company_profile` | `companies.company_profile` (JSON) | N/A — stored on company row | `extract_company_profile()` in `extraction.py` |
| `website_clean_text` | `companies.website_clean_text` | `website_text_cache.url_hash` | None (scraped, not LLM) |
| `transcript_clean` | `companies.transcript_clean` | `audio_transcript_cache.file_content_hash` | Whisper API (`transcribe_audio()` in `preprocessing.py`) |
| `funding_program_rules` | `funding_program_guidelines_summary.rules_json` (JSON) | `source_file_hash` (combined hash) | `extract_rules_from_text()` in `guidelines_processing.py` |
| `style_profile` | `alte_vorhabensbeschreibung_style_profile.style_summary_json` (JSON) | `combined_hash` | `generate_style_profile()` in `style_extraction.py` |

**All inputs are optional.** Generation proceeds with whatever context is available. Missing inputs produce less accurate output; they do not cause errors.

### 4.2 Batch Generation — `_generate_batch_content()`

Located in `documents.py:1031`.

```
POST /documents/{id}/generate-content
    │
    ├── Load document, company, funding program, style profile
    ├── Filter out milestone_table sections (never generated by LLM)
    ├── Split remaining sections into batches of 3–5
    │
    └── For each batch:
        ├── [Token logging] len(prompt) // 4
        ├── Build prompt: Rules → Company → Style → Task
        │     Rules:   funding_program_rules dict → formatted block
        │     Company: company_profile + website_clean_text[:30000] + transcript_clean[:30000]
        │     Style:   style_profile patterns → formatted block
        │     Task:    list of section headings to generate
        ├── Call OpenAI (gpt-4o-mini, temp=0.7, response_format=json_object, timeout=120s)
        ├── Validate JSON: all expected section IDs present, all values are strings
        ├── On structural failure: retry up to 2 additional times (3 calls total worst case)
        └── Merge generated content into document.content_json.sections
```

### 4.3 Section Edit — `_generate_section_content()`

Located in `documents.py:2046`.

```
POST /documents/{id}/chat  [message targets a specific section]
    │
    ├── Identify target section from message (regex + fuzzy matching)
    ├── instruction_text = instruction or ""   [None guard]
    ├── [Token logging] len(prompt) // 4
    ├── Build prompt:
    │     Style guide
    │     Role: EDITOR not AUTHOR
    │     Current section content (must exist)
    │     Benutzeranweisung: <user_instruction>{instruction_text}</user_instruction>
    │     Company context (support only)
    ├── Call OpenAI (gpt-4o-mini, temp=0.7, max_tokens=2000, timeout=120s)
    ├── Strip markdown artifacts via regex
    └── Return suggested_content (NOT saved yet)
    │
    └── POST /documents/{id}/chat/confirm  [user clicks Approve]
        └── Update section.content only — section.title is NEVER modified
```

### 4.4 Q&A — `_answer_question_with_context()`

Located in `documents.py:2379`.

```
POST /documents/{id}/chat  [message is a question]
    │
    ├── user_query_text = user_query or ""   [None guard]
    ├── Assemble context: full document text + website summary + last 3 chat messages
    ├── [Token logging] len(prompt) // 4
    ├── Build prompt:
    │     Context block
    │     BENUTZERFRAGE: <user_instruction>{user_query_text}</user_instruction>
    ├── Call OpenAI (gpt-4o-mini, temp=0.7, max_tokens=1000, timeout=120s)
    └── Return answer (no database write)
```

### 4.5 Prompt Injection Mitigation

User-controlled strings (`instruction`, `user_query`) are wrapped with XML delimiters before prompt injection:

```xml
<user_instruction>
{user_input}
</user_instruction>
```

This is applied at `documents.py:2157–2159` (instruction) and `documents.py:2422–2424` (user_query). None guards (`x or ""`) are applied immediately before wrapping.

### 4.6 Token Logging

All six LLM call sites log prompt size before each API call:

```python
approx_tokens = len(prompt) // 4
logger.info("LLM {step} prompt size (chars): %s", len(prompt))
logger.info("LLM {step} prompt tokens: %s", approx_tokens)
```

Step labels and locations:

| Label | File | Line |
|-------|------|------|
| `batch generation` | `documents.py` | ~1201 |
| `section edit` | `documents.py` | ~2206 |
| `Q&A` | `documents.py` | ~2440 |
| `company profile extraction` | `extraction.py` | ~132 |
| `guideline extraction` | `guidelines_processing.py` | ~109 |
| `style extraction` | `style_extraction.py` | ~94 |

---

## 5. Database Schema

### 5.1 Entity-Relationship Summary

```
users (PK: email)
  │
  ├──< funding_programs (FK: user_email)
  │         │
  │         ├──< funding_program_companies >──┐
  │         ├──< funding_program_documents    │
  │         └──< funding_program_guidelines_summary
  │                                           │
  ├──< companies (FK: user_email) ───────────┘
  │         │
  │         ├──< documents (FK: company_id, funding_program_id)
  │         │         └── template_id → user_templates
  │         └──< company_documents
  │
  └──< user_templates (FK: user_email)

files (standalone, PK: UUID, unique: content_hash)
  ├── funding_program_documents.file_id
  ├── company_documents.file_id
  └── alte_vorhabensbeschreibung_documents.file_id

Cache tables (no FK relationships, keyed by hash):
  audio_transcript_cache (key: file_content_hash)
  website_text_cache (key: url_hash)
  document_text_cache (key: file_content_hash)

Style profile:
  alte_vorhabensbeschreibung_documents → (combined hash) → alte_vorhabensbeschreibung_style_profile
```

### 5.2 Full Column Reference

#### `users`
| Column | Type | Constraint |
|--------|------|-----------|
| `email` | String | PK, index |
| `password_hash` | String | NOT NULL |
| `created_at` | DateTime(tz) | NOT NULL, server_default=now() |
| `reset_token_hash` | String | nullable |
| `reset_token_expiry` | DateTime(tz) | nullable |

#### `funding_programs`
| Column | Type | Constraint |
|--------|------|-----------|
| `id` | Integer | PK, autoincrement |
| `title` | String | NOT NULL |
| `website` | String | nullable |
| `created_at` | DateTime(tz) | NOT NULL, server_default=now() |
| `user_email` | String | FK→users.email, index |

#### `funding_program_companies` (join table)
| Column | Type | Constraint |
|--------|------|-----------|
| `funding_program_id` | Integer | FK→funding_programs.id, PK |
| `company_id` | Integer | FK→companies.id, PK |
| — | — | UniqueConstraint(funding_program_id, company_id) |

#### `companies`
| Column | Type | Constraint |
|--------|------|-----------|
| `id` | Integer | PK, autoincrement |
| `name` | String | NOT NULL |
| `website` | String | nullable |
| `audio_path` | String | nullable |
| `website_text` | String | nullable — legacy, kept for backward compat |
| `transcript_text` | String | nullable — legacy |
| `website_raw_text` | Text | nullable — raw scraped |
| `website_clean_text` | Text | nullable — boilerplate removed |
| `transcript_raw` | Text | nullable — raw Whisper output |
| `transcript_clean` | Text | nullable — filler words removed |
| `processing_status` | String | server_default="pending" |
| `processing_error` | String | nullable |
| `created_at` | DateTime(tz) | NOT NULL, server_default=now() |
| `updated_at` | DateTime(tz) | NOT NULL, onupdate=now() |
| `user_email` | String | FK→users.email, NOT NULL, index |
| `company_profile` | JSON | nullable — LLM-extracted structured facts |
| `extraction_status` | String | nullable: "pending"/"extracted"/"failed" |
| `extracted_at` | DateTime(tz) | nullable |

#### `documents`
| Column | Type | Constraint |
|--------|------|-----------|
| `id` | Integer | PK, autoincrement |
| `company_id` | Integer | FK→companies.id, NOT NULL, index |
| `type` | String | NOT NULL, index ("vorhabensbeschreibung"/"vorkalkulation") |
| `content_json` | JSON | NOT NULL |
| `chat_history` | JSON | nullable |
| `updated_at` | DateTime(tz) | NOT NULL, onupdate=now() |
| `headings_confirmed` | Integer | NOT NULL, server_default="0" — 0/1, not boolean |
| `funding_program_id` | Integer | FK→funding_programs.id, nullable, index |
| `template_id` | UUID | FK→user_templates.id, nullable, index |
| `template_name` | String | nullable — system template name |
| `title` | String | nullable |

**`content_json` shape:**
```json
{
  "sections": [
    { "id": "1", "title": "1. Einleitung", "content": "..." },
    { "id": "1.1", "title": "1.1 Kontext", "content": "...", "type": "text" },
    {
      "id": "4",
      "title": "4. Meilensteine",
      "content": "",
      "type": "milestone_table",
      "milestone_data": { "milestones": [...], "total_expenditure": 50000 }
    }
  ]
}
```

All section IDs are strings. Sections without `type` are treated as `"text"`. `milestone_table` sections are excluded from LLM generation.

#### `files`
| Column | Type | Constraint |
|--------|------|-----------|
| `id` | UUID | PK, index |
| `content_hash` | Text | UNIQUE, NOT NULL, index |
| `file_type` | Text | nullable ("audio"/"pdf"/"docx"/"doc") |
| `storage_path` | Text | NOT NULL — Supabase path |
| `size_bytes` | Integer | NOT NULL |
| `created_at` | DateTime(tz) | NOT NULL, server_default=now() |

#### `user_templates`
| Column | Type | Constraint |
|--------|------|-----------|
| `id` | UUID | PK |
| `name` | String | NOT NULL |
| `description` | Text | nullable |
| `template_structure` | JSON | NOT NULL — must contain `"sections"` array |
| `user_email` | String | FK→users.email, NOT NULL, index |
| `created_at` / `updated_at` | DateTime(tz) | standard |

#### Cache tables (`audio_transcript_cache`, `website_text_cache`, `document_text_cache`)

All three have the same pattern: UUID PK, hash key (unique, indexed), cached text (Text NOT NULL), `created_at`, `processed_at`. No TTL, no foreign keys. Invalidation is by hash change.

#### `funding_program_guidelines_summary`
| Column | Type | Constraint |
|--------|------|-----------|
| `id` | UUID | PK |
| `funding_program_id` | Integer | FK→funding_programs.id, UNIQUE |
| `rules_json` | JSON | NOT NULL |
| `source_file_hash` | Text | NOT NULL — SHA-256 of sorted combined file hashes |
| `created_at` / `updated_at` | DateTime(tz) | standard |

One row per funding program. Regenerated when `source_file_hash` changes.

#### `alte_vorhabensbeschreibung_style_profile`
| Column | Type | Constraint |
|--------|------|-----------|
| `id` | UUID | PK |
| `combined_hash` | Text | UNIQUE — SHA-256 of sorted source file hashes |
| `style_summary_json` | JSON | NOT NULL |
| `created_at` / `updated_at` | DateTime(tz) | standard |

One active row (the most recent hash). A new row is written when the source document set changes. Old rows are not automatically deleted.

---

## 6. Async Processing

### 6.1 Mechanism

FastAPI `BackgroundTasks` is a thin wrapper around Starlette's background task queue. It does **not** use asyncio. Tasks are **synchronous Python functions** called by Uvicorn's thread pool after the HTTP response is sent.

```python
# In route handler:
background_tasks.add_task(process_company_background, company_id=..., website=..., audio_path=...)
# Response is returned to client immediately
# process_company_background() runs in a threadpool worker afterward
```

### 6.2 `process_company_background()` — Full Sequence

Located in `companies.py:166`. Creates its **own database session** (does not reuse the request session):

```
1.  Open new SessionLocal()
2.  Load Company from DB
3.  Set processing_status = "processing", commit
4.  If website:
      scrape_about_page(website, db)  ← website_scraping.py
        ├── Check website_text_cache (by url_hash)
        │     HIT  → return cached text
        │     MISS → requests.get() up to 20 pages (10s timeout per page)
        │          → store in website_text_cache
        └── clean_website_text()  ← text_cleaning.py
      Set company.website_raw_text, website_clean_text, website_text (legacy)
5.  If audio_path:
      If audio_path looks like UUID (file_id):
        download file from Supabase Storage to tempfile
        transcribe_audio(tmp_path, file_content_hash, db)  ← preprocessing.py
          ├── Check audio_transcript_cache (by content_hash)
          │     HIT  → return cached transcript
          │     MISS → OpenAI Whisper API (language="de", timeout=300s)
          │          → store in audio_transcript_cache
          └── delete tempfile
      Else (legacy local path):
        transcribe_audio(local_path, file_content_hash=None, db)
        [cache not used for legacy paths — no content_hash available]
      clean_transcript()  ← text_cleaning.py
      Set company.transcript_raw, transcript_clean, transcript_text (legacy)
6.  Set processing_status = "done", commit
7.  If has_text_data AND not already_extracted:
      extract_company_profile(website_text, transcript_text)  ← extraction.py
        └── OpenAI LLM call (gpt-4o-mini, temp=0.0, json_object, timeout=60s)
      Set company.company_profile, extraction_status="extracted", commit
8.  On any exception: set processing_status = "failed", processing_error = message
9.  Close session
```

**Status values written to `companies.processing_status`:**

| Status | Set when |
|--------|---------|
| `"pending"` | Default on creation |
| `"processing"` | Start of background task |
| `"done"` | Website + audio processing complete (step 6) |
| `"failed"` | Any unrecoverable exception |

Note: Profile extraction (step 7) runs **after** `processing_status` is set to `"done"`. A failed extraction sets `extraction_status = "failed"` but does **not** revert `processing_status` to `"failed"`. The frontend considers `"done"` as the terminal state and does not wait for extraction.

### 6.3 Frontend Polling

```
EditorPage mounts
    │
    ├── Check company.processing_status
    │
    ├── If "done" or "failed": stop
    │
    └── Else: setInterval(() => GET /companies/{id}, 2000ms)
              On response: update company state
              If "done" or "failed": clearInterval()
```

There is no server-push mechanism (WebSockets, SSE). The 2-second poll interval is hardcoded at `EditorPage.tsx:453`. No backoff is applied.

### 6.4 Guideline Processing

Guidelines are processed synchronously within the request handler in `funding_programs.py`:

```
POST /funding-programs/{id}/guidelines (upload file)
    │
    ├── get_or_create_file()  → upload to Supabase, create files record
    ├── extract_document_text()  → check document_text_cache → PyPDF2/python-docx
    ├── store_document_text()  → write to document_text_cache
    └── process_guidelines_for_funding_program()  → guidelines_processing.py
          ├── Compute combined hash of all guideline file hashes
          ├── If hash unchanged: return existing summary (skip LLM)
          └── If hash changed: extract_rules_from_text() → OpenAI LLM
                └── Update funding_program_guidelines_summary
```

This is **synchronous and blocks the request**. Uploading a large PDF with many guideline pages will hold the HTTP connection open until the LLM call completes (up to 120 seconds timeout).

---

## 7. External Services

### 7.1 OpenAI API

**Used for:** Text generation, chat editing, Q&A, company profile extraction, guidelines extraction, style profile extraction, and audio transcription (Whisper).

**Client initialisation pattern** (repeated in each module that uses it):
```python
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)
```

There is no shared client instance. Each module creates its own. Whisper uses `client.audio.transcriptions`, all other calls use `client.chat.completions`.

**All LLM models used:**

| Call | Model | Endpoint |
|------|-------|---------|
| Text generation, editing, Q&A, extraction | `gpt-4o-mini` | `chat.completions` |
| Audio transcription | `whisper-1` | `audio.transcriptions` |

**Timeouts:**

| Call | Timeout |
|------|---------|
| Company profile extraction | 60s |
| Style extraction | 180s |
| Guideline extraction | 120s |
| Batch content generation | 120s |
| Section edit | 120s |
| Q&A | 120s |
| Audio transcription | 300s |

**Failure mode:** If `OPENAI_API_KEY` is absent, `extraction.py` raises `ValueError` immediately. `preprocessing.py:transcribe_audio` logs an error and returns `None` (soft failure — does not block company creation). `documents.py` raises `ValueError` before making any API call if the key is not set.

### 7.2 Supabase Storage

**Used for:** Storing uploaded files (audio, PDF, DOCX).

**Configuration:**
```
SUPABASE_URL          → Supabase project URL
SUPABASE_KEY          → service_role key (bypasses Row-Level Security)
SUPABASE_STORAGE_BUCKET → bucket name (default: "files")
```

**Storage path format:** `{file_type}/{hash[:2]}/{sha256_hash}.{ext}`
Example: `pdf/ab/abcd1234ef567890....pdf`

**Failure mode:** If Supabase is not configured, `get_or_create_file()` raises an exception — file uploads fail with HTTP 500. The application does not fall back to local storage for uploaded files in production. In development without Supabase, file features are unavailable.

**Note:** Audio files for transcription are downloaded from Supabase to a `tempfile`, transcribed, then the temp file is deleted in a `finally` block.

### 7.3 PostHog Analytics

**Used for:** Event tracking on user registration and login.

**Configuration:**
```
POSTHOG_API_KEY    → API key (optional)
POSTHOG_HOST       → ingest host (default: "https://us.i.posthog.com")
POSTHOG_DISABLED   → "true" to disable (default: "false")
```

**Lifecycle:** Initialised in the FastAPI `lifespan` context manager at startup (`init_posthog()`). Flushed and shut down cleanly on app shutdown (`shutdown_posthog()`).

**Failure isolation:** All PostHog calls are wrapped in `try/except`. Analytics failures never block authentication or any other feature.

**Events captured:**
- `user_signed_up` — on successful registration
- `user_logged_in` — on successful login

---

## 8. File Storage Architecture

```
User uploads file
        │
        ▼
get_or_create_file(db, file_bytes, file_type)
        │
        ├── compute_file_hash(file_bytes)  → SHA-256 hex string
        │
        ├── SELECT FROM files WHERE content_hash = ?
        │         │
        │    EXISTS → return existing File record (is_new=False)
        │    MISSING ↓
        │
        ├── upload_to_supabase_storage(file_bytes, file_type, content_hash)
        │         └── path: {type}/{hash[:2]}/{hash}.{ext}
        │
        └── INSERT INTO files (id=uuid4, content_hash, file_type, storage_path, size_bytes)
            return new File record (is_new=True)
```

**Deduplication:** The same file uploaded twice results in one `files` row and one Supabase object. The second upload returns the existing record immediately.

**Download path:**
```
GET /documents/{id}/export  (or any endpoint serving file bytes)
        │
        ▼
download_from_supabase_storage(storage_path)
        └── supabase.storage.from_(bucket).download(path) → bytes
```

---

## 9. Template System

### 9.1 Resolution Priority

```
Document has template_id (UUID)?
    YES → resolve_template(source="user", ref=template_id, user_email=...)
              └── SELECT FROM user_templates WHERE id=? AND user_email=?
    NO  ↓
Document has template_name (String)?
    YES → resolve_template(source="system", ref=template_name)
              └── get_system_template(template_name)  ← app/templates/__init__.py
    NO  ↓
Default → resolve_template(source="system", ref="wtt_v1")
```

### 9.2 System Templates

Python modules in `backend/app/templates/`. Currently only `wtt_v1`. Each must be registered in `backend/app/templates/__init__.py`. Return a dict with shape:
```python
{
  "sections": [
    {"id": "1", "title": "1. Einleitung", "content": ""},
    ...
  ]
}
```

### 9.3 User Templates

Stored in `user_templates` table. `template_structure` JSON must have a `"sections"` key with a list value. Ownership is enforced in the resolver (user_email must match).

---

## 10. Alembic Migration Chain

Migrations in `backend/alembic/versions/` (abbreviated, oldest → newest):

```
1bdfd9e377ca  initial_schema
add_files_table
f5c86d23bbfc  add_user_ownership_to_funding_programs
d1e2f3a4b5c6  extend_company_model
0fb7cad86248  add_company_profile_extraction_fields
94fe78de25e3  add_funding_program_scraping_fields
b7c8d9e0f1a2  remove_funding_program_scraping_fields
a1b2c3d4e5f6  add_funding_program_documents
add_processing_cache_tables
c9d0e1f2a3b4  add_funding_program_guidelines_summary
55cd193493bc  add_phase_2_5_template_system
5118cacae937  add_template_fields_and_constraints
f6g7h8i9j0k1  add_template_fields_to_documents
378640cd9ae5  add_headings_confirmed_to_documents
e2f3a4b5c6d7  add_alte_vorhabensbeschreibung
add_chat_history_to_documents
a2b3c4d5e6f7  allow_multiple_docs_per_company_program
8a8eb899811f  add_missing_guidelines_columns
```

**Known issue:** `add_chat_history_to_documents` was added as a named file without a proper revision chain. The `_safe_get_document_by_id()` function in `documents.py` (lines 44–125) implements a three-strategy fallback (ORM → deferred column → raw SQL) to handle databases where this column may be missing. Do not remove this fallback until the migration is verified in all environments.

---

## 11. What Breaks and Why

| If you do this | What breaks |
|----------------|------------|
| Add a new router with prefix `companies` or `documents` | SPA catch-all will incorrectly 404 — add prefix to skip list in `main.py:205` |
| Remove `get_current_user` from an endpoint | Endpoint becomes unauthenticated — ownership checks inside the handler will also fail |
| Change `content_json` section structure | Editor `EditorPage.tsx`, all generation/edit functions, and export renderers all assume `{id, title, content}` — will silently produce wrong output |
| Change `headings_confirmed` from Integer to Boolean | SQLite compatibility breaks — the column is intentionally Integer |
| Use `db.commit()` inside a background task before `process_company_background` finishes | Fine — the background task opens its own session. But the request's session is already closed at this point. |
| Call `_generate_batch_content()` from the `/chat` endpoint | Will create content from scratch using empty-section prompts — section editing will not work correctly. These two functions have different roles and different prompt structures. |
| Remove XML delimiters from `instruction` or `user_query` before LLM injection | Re-opens the prompt injection vulnerability at `documents.py:2157` and `documents.py:2422` |
| Set `Base.metadata.create_all()` unconditionally at startup | Runs on PostgreSQL in production, potentially conflicting with Alembic-managed schema |
| Add a new API route prefix without registering it in the Alembic-unrelated skip list | Not a schema issue but SPA routing will try to serve `index.html` for it |
