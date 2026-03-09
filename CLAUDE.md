# Claude Development Rules

You are working on a production-grade AI document generation system.

This repository powers a deployed application used by real clients.
Code changes must prioritize safety, clarity, and incremental improvements.

## Development Principles

1. Never perform large refactors without explicit approval.
2. Prefer small, incremental improvements over architectural rewrites.
3. Do not modify database schema unless explicitly requested.
4. Do not run migrations automatically.
5. Do not modify environment variables.
6. Do not modify deployment scripts (Render, Docker) unless instructed.

## Code Quality

- Follow clean architecture principles.
- Avoid modifying unrelated files.
- Do not duplicate logic.
- Keep functions focused and readable.

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

## Frontend

Frontend uses:
- React
- TypeScript
- Vite

When modifying frontend code:
- maintain existing UX flows
- avoid introducing new global state
- prefer small component improvements

## AI Generation System

The application generates funding program documents using LLMs.

Important rules:

- Minimize token usage.
- Avoid injecting unnecessary context into prompts.
- Maintain deterministic outputs when possible.
- Do not increase temperature or token limits without justification.

## Security

Always consider:

- prompt injection
- SSRF
- rate limiting
- sensitive data leakage

Never log sensitive company data.

## Workflow

Before implementing any change:

1. explain the problem
2. propose the change
3. show a diff
4. wait for approval

## Documentation hierarchy

When making changes to this repository, consult documents in the following order:

1. PRODUCT_REQUIREMENTS.md — defines product goals and workflow
2. SYSTEM_ARCHITECTURE.md — defines system components and responsibilities
3. AGENTS.md — defines specialized agent roles
4. CLAUDE.md — defines coding rules and constraints

## Large files

documents.py is very large. When working on this file,
read only the relevant function instead of loading the entire file
unless absolutely necessary.

If code behavior conflicts with these documents, follow the architecture and product documents.

Never directly modify files without explanation.