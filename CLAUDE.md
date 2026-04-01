# Claude Development Rules

You are working on a production-grade RAG-powered AI document generation system.

This repository powers a deployed application used by real clients.
Code changes must prioritize safety, clarity, and incremental improvements.

---

## Canonical Backend

**`backend/innovo_backend/` is the single source of truth for all backend code.**

- All new routes, services, models, and logic go in `backend/innovo_backend/`
- `backend/innovo_backend/main.py` is the entry point
- `/backend/app/` is the legacy monolith — read-only reference only. Never add to it.
- Services in `innovo_backend/services/` import only from `innovo_backend/shared/`
- Services never import from each other

---

## System Constants (Never Change Without Migration)

```
EMBEDDING_MODEL     = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
```

The embedding model is used for every chunk ingestion and every retrieval query across the system. **Never change it without running a full re-embedding migration** on all `knowledge_base_chunks` rows. Mixing models makes cosine similarity meaningless.

---

## Development Principles

1. Never perform large refactors without explicit approval.
2. Prefer small, incremental improvements over architectural rewrites.
3. Do not modify database schema unless explicitly requested. **Exception:** The following v2 migrations are pre-approved: `projects` table, `project_contexts` table, `knowledge_base_documents` table, `knowledge_base_chunks` table, `project_id` FK on `documents`. All other schema changes still require explicit approval.
4. Do not run migrations automatically.
5. Do not modify environment variables.
6. Do not modify deployment scripts (Render, Docker) unless instructed.

---

## Code Quality

- Follow clean architecture principles.
- Avoid modifying unrelated files.
- Do not duplicate logic.
- Keep functions focused and readable.

---

## Backend

Backend uses:
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL in production

When modifying backend code:
- preserve API contracts
- avoid changing response shapes
- avoid breaking existing endpoints
- keep routers thin — business logic belongs in service files

---

## RAG Pipeline Rules

This system is RAG-powered. Every ingestion source goes through:
**EXTRACT → CHUNK → EMBED → STORE**

Hard rules:
1. **Single embedding model** — `text-embedding-3-small` only. Documented above.
2. **Chunking is mandatory** — never store a raw document as a single vector.
3. **Scoped retrieval** — every vector search must filter by `company_id`, `funding_program_id`, or `project_id`. Global unfiltered search is forbidden.
4. **Ingestion idempotency** — before inserting chunks for a source, delete existing chunks for that `source_id`. Never append.
5. **Generation idempotency** — re-generating a section overwrites existing content. Never appends.
6. **Cache-first** — check `website_text_cache`, `audio_transcript_cache`, `document_text_cache` before processing. Never re-process the same content.

---

## Frontend

Frontend uses:
- React
- TypeScript
- Vite

When modifying frontend code:
- maintain existing UX flows
- avoid introducing new global state
- prefer small component improvements
- all HTTP calls go through `frontend/src/utils/api.ts` only

---

## AI Generation System

The application generates funding documents using per-section RAG generation.

Important rules:
- minimize token usage
- avoid injecting unnecessary context into prompts
- prefer structured outputs when possible
- do not increase temperature or token limits without justification
- do not change prompt block order without testing — it is load-bearing
- `milestone_table` sections must never be sent to the LLM
- section titles must never be modified by LLM suggestions

---

## Security

Always consider:
- **Prompt injection** — wrap all user inputs in XML delimiters before prompt injection
- **SSRF** — validate all external request URLs against RFC 1918 ranges before connecting
- **Rate limiting** — no endpoint is rate-limited; be mindful of LLM abuse vectors
- **Sensitive data leakage** — never log prompt content, section text, company data, or user queries

---

## Workflow

Before implementing any change:

1. explain the problem
2. propose the solution
3. identify the files that need modification
4. show the proposed diff
5. wait for approval before modifying code

---

## Documentation Hierarchy

When modifying the repository, consult documents in this order:

1. **docs/PRODUCT_VISION.md** — product philosophy and design principles
2. **PRODUCT_REQUIREMENTS.md** — defines product purpose and workflows
3. **SYSTEM_ARCHITECTURE.md** — explains system design, RAG pipeline, and components
4. **CODEBASE_OVERVIEW.md** — describes repository structure and file tree
5. **DEVELOPMENT_RULES.md** — engineering rules and coding discipline
6. **AGENTS.md** — specialized agent responsibilities
7. **CLAUDE.md** — behavior rules for Claude

If conflicts arise, follow **product and architecture documents first**.

---

## Agent Usage

Before modifying code, determine which specialized agent should handle the task.

Agents are defined in `.claude/agents/`. Select the agent whose responsibility matches the task area before making changes.

---

## Large Files

`/backend/app/routers/documents.py` is ~3,300 lines and **legacy — do not modify**.

For the canonical document service:
`backend/innovo_backend/services/documents/service.py` — read only the relevant function.

---

## Safety Rule

Never modify files directly without first explaining the change and waiting for approval.
