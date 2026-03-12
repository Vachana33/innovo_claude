# Claude Development Rules

You are working on a production-grade AI document generation system.

This repository powers a deployed application used by real clients.
Code changes must prioritize safety, clarity, and incremental improvements.

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

---

## AI Generation System

The application generates funding program documents using LLMs.

Important rules:

- minimize token usage
- avoid injecting unnecessary context into prompts
- prefer structured outputs when possible
- do not increase temperature or token limits without justification

---

## Security

Always consider:

- prompt injection
- SSRF
- rate limiting
- sensitive data leakage

Never log sensitive company data.

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
3. **SYSTEM_ARCHITECTURE.md** — explains system design and components
4. **CODEBASE_OVERVIEW.md** — describes repository structure
5. **DEVELOPMENT_RULES.md** — engineering rules and coding discipline
6. **AGENTS.md** — specialized agent responsibilities
7. **CLAUDE.md** — behavior rules for Claude

If conflicts arise, follow **product and architecture documents first**.

---

## Agent Usage

Before modifying code, determine which specialized agent should handle the task.

Agents are defined in:

`.claude/agents/`

Select the agent whose responsibility matches the task area before making changes.

---

## Large Files

`documents.py` is extremely large.

When working with it:

- read only the relevant function
- avoid loading the entire file unless absolutely necessary

---

## Safety Rule

Never modify files directly without first explaining the change and waiting for approval.