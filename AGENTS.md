# Project Agents

This repository uses specialized agents for different areas of the system.

Each agent has its own rule set located in:

`.claude/agents/`

Agents should be invoked when a task falls within their responsibility area.

---

## Backend Agent

Location: `.claude/agents/backend_agent.md`

Responsible for:

- FastAPI routers in `innovo_backend/services/*/router.py`
- Database queries and SQLAlchemy models in `innovo_backend/shared/models.py`
- Service-layer logic in `innovo_backend/services/*/service.py`
- Shared modules in `innovo_backend/shared/`
- Database migrations in `backend/alembic/versions/`
- API performance improvements

Focus:

- maintain API stability
- keep routers thin — business logic in service files
- services import only from `shared/`, never from each other
- all new code goes in `innovo_backend/`, not `/backend/app/`

---

## LLM Pipeline Agent

Location: `.claude/agents/llm_pipeline_agent.md`

Responsible for:

- RAG ingestion pipeline (Extract → Chunk → Embed → Store)
- Embedding calls — `services/knowledge_base/retriever.py`
- Vector retrieval and source scoping
- Per-section generation — `services/documents/service.py`
- Chat-based RAG refinement — `services/projects/chat_service.py`
- Context assembly — `services/projects/context_assembler.py`
- Prompt construction — `services/documents/prompt_builder.py`
- Extraction LLM calls — `shared/extraction.py`, `shared/guidelines_processing.py`, `shared/style_extraction.py`
- Token optimisation
- Generation pipeline reliability
- Structured output enforcement

Focus:

- single embedding model: `text-embedding-3-small` (1536 dimensions) — never change without re-embedding migration
- every vector search must be scoped by company_id, funding_program_id, or project_id — no global search
- ingestion idempotency: delete existing chunks for source_id before inserting new ones
- generation idempotency: overwrite section content, never append
- cache-first: check website, audio, and document text caches before processing
- prompt block order is load-bearing — do not reorder without testing
- all user inputs in prompts must be XML-delimited

---

## Frontend Agent

Location: `.claude/agents/frontend_agent.md`

Responsible for:

- React components and pages in `frontend/src/`
- UI improvements
- API integration via `frontend/src/utils/api.ts`
- Frontend performance
- User experience improvements

Focus:

- maintain existing UI patterns
- avoid unnecessary re-renders
- all HTTP calls through `src/utils/api.ts` only — no raw fetch()
- `AuthContext` is the only global state — do not add new Contexts
- `ProtectedRoute` must wrap all authenticated pages
- avoid introducing new global state

---

## Security Agent

Location: `.claude/agents/security_agent.md`

Responsible for:

- authentication and JWT handling
- input validation at API boundaries
- SSRF prevention — all external URL requests must validate against RFC 1918 ranges
- prompt injection mitigation — XML delimiters on all user inputs in prompts
- rate limiting considerations
- sensitive data exposure prevention — no logging of prompt content, company data, section text

Focus:

- protecting user data
- preventing API abuse
- ensuring outbound HTTP requests never target user-supplied URLs without validation
- ensuring password reset tokens are not exposed in API responses in production
