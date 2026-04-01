# Development Rules

These rules define how code should be modified in this repository.

They exist to ensure safe, predictable changes when AI agents or engineers work on the system.

This file focuses on **engineering discipline**. For product logic, see `PRODUCT_REQUIREMENTS.md`.
For architecture, see `SYSTEM_ARCHITECTURE.md`.

---

## 1. General Principles

Always prioritise:
- stability
- clarity
- incremental improvements

Do not introduce large changes unless explicitly requested.
Prefer **small, localised modifications** that preserve existing behaviour.

---

## 2. Change Discipline

Before implementing any change:

1. Explain the problem.
2. Propose the solution.
3. Identify the files that must be modified.
4. Keep the change minimal and isolated.

Avoid touching unrelated files.

---

## 3. Canonical Backend — innovo_backend/

All active development belongs in `backend/innovo_backend/`.

**Rules:**
- All new routes, services, models, and business logic go in `backend/innovo_backend/`
- `/backend/app/` is legacy — read-only reference only. Never add to it.
- If a feature exists in `/backend/app/` but not in `innovo_backend/`, port it cleanly. Do not copy-paste the legacy code.
- Services in `innovo_backend/services/` import only from `innovo_backend/shared/`. Services never import from each other.
- `shared/models.py` is the single source of truth for all SQLAlchemy models.
- `shared/schemas.py` is the source of truth for all shared Pydantic schemas. Service-specific schemas live inside the service folder.

---

## 4. Code Organisation

### Backend

- Keep routers thin — route handlers contain no business logic.
- Place business logic in service files (`service.py`) within each service directory.
- Pattern: `router → service → shared modules → database`

### Frontend

- Keep pages focused on layout and composition.
- Move reusable logic into components or utilities.
- All HTTP calls go through `frontend/src/utils/api.ts`. No raw `fetch()` calls anywhere else.

---

## 5. RAG Pipeline Rules (Hard Rules)

These rules govern the ingestion and retrieval pipeline. Violating them degrades generation quality or breaks retrieval silently.

### 5.1 Single Embedding Model

```
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
```

Every embed call across the entire system uses this model and these dimensions. This is a constant, not a configuration option.

**Never change the embedding model without running a full re-embedding migration** on every row in `knowledge_base_chunks`. Mixing models makes cosine similarity meaningless — retrieval returns garbage without any error.

### 5.2 Chunking Is Not Optional

Every ingested text source must be chunked before embedding. Raw full-document text must never be stored as a single vector — retrieval quality degrades severely.

Chunking rules:
- Never split mid-sentence
- Never split mid-section
- Prepend the parent section heading to each chunk's text
- Chunk size and overlap must be consistent per document type

### 5.3 Source Scoping on Retrieval (Mandatory)

Every vector similarity search must filter by at least one of:
- `company_id`
- `funding_program_id`
- `project_id`

**Global unfiltered vector search is forbidden.** It returns chunks from unrelated companies and projects, degrading generation quality and creating data isolation violations.

### 5.4 Ingestion Idempotency

Re-running ingestion for the same source must not create duplicate chunks.

Protocol: before inserting new chunks for a source, **delete all existing chunks where `source_id = this source_id`**. Then insert fresh chunks. Never append to existing chunks for the same source.

### 5.5 Generation Idempotency

Re-generating a section must **overwrite** the existing content record, never append. Each section has one canonical content record — update it in place.

### 5.6 Cache-First Processing

Before scraping a URL → check `website_text_cache` (key: SHA-256 of normalised URL).
Before transcribing audio → check `audio_transcript_cache` (key: file content hash).
Before extracting a document → check `document_text_cache` (key: file content hash).

If cache hit and not stale → use cached text. Do not re-process.
If cache miss or stale (URLs stale after 30 days) → process and update cache.

**This is a hard rule.** Re-processing the same content wastes tokens and produces non-deterministic embedding differences.

---

## 6. Refactoring Rules

Refactoring is allowed only when it is **small and safe**.

Good refactors:
- extracting helper functions
- improving naming
- simplifying conditional logic
- reducing duplicated code

Avoid:
- rewriting entire modules
- reorganising or renaming existing folder structures
- changing public interfaces

Creating new directories within `innovo_backend/services/` for new services is permitted. Reorganising or renaming existing directories is not.

---

## 7. Database Safety

Database changes are high risk.

Do not:
- modify schemas
- add migrations
- remove columns

unless explicitly requested.

All existing database contracts must remain stable.

**v2 exception:** The following migrations are pre-approved: `projects` table, `project_contexts` table, `knowledge_base_documents` table, `knowledge_base_chunks` table, `project_id` FK on `documents`. All other schema changes require explicit approval.

Never modify existing migration files — add new ones only.

---

## 8. API Stability

Existing API endpoints must remain compatible.

Do not:
- change request formats
- change response shapes
- rename fields returned to the frontend

unless the change is explicitly requested.

---

## 9. AI Generation Safety

When modifying the LLM pipeline:

- Do not increase prompt size unnecessarily
- Do not send unused context to the model
- Preserve structured outputs when possible
- Do not change prompts unless the improvement is clearly justified
- Do not change the prompt block order without testing — it is load-bearing
- Do not remove `<user_instruction>` XML delimiters from user input injections
- Do not lower generation temperature below 0.7 for generation and chat refinement calls
- `milestone_table` sections must never be sent to the LLM
- Section titles must never be modified by LLM suggestions — content only

---

## 10. Security Awareness

Always consider:

- **Prompt injection** — all user inputs must be XML-delimited before prompt injection
- **SSRF** — all external HTTP requests must validate the target URL against RFC 1918 private IP ranges before connecting. `allow_redirects` compounds this risk.
- **Sensitive data exposure** — never log prompt content, section text, company data, or user queries. Log only IDs, lengths, and status codes.

Never log private company data or document contents.

---

## 11. Scope Control

Every change must remain **within the scope of the requested task**.

Do not introduce:
- unrelated refactors
- new dependencies
- architectural changes

unless explicitly approved.
