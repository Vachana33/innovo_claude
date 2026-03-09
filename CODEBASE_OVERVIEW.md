# Codebase Overview

## Backend

Location: `backend/`

Main entrypoint:
backend/main.py

Key directories:

backend/app/routers/        → API endpoints  
backend/app/models.py       → SQLAlchemy models  
backend/app/database.py     → DB connection  
backend/app/llm/            → LLM pipeline modules  
backend/app/templates/      → system templates  

Large files:
documents.py (~3300 lines)

---

## Frontend

Location: `frontend/`

Key directories:

frontend/src/pages/         → application pages  
frontend/src/components/    → reusable UI components  
frontend/src/utils/api.ts   → centralized API client  
frontend/src/contexts/      → global state (AuthContext)

Core page:
EditorPage.tsx → document editing interface

---

## Engineering Documentation

Additional engineering guides are located in the `docs/` directory.

Examples include:

- AUTHENTICATION_SETUP.md
- OBSERVABILITY_LOGGING.md
- SECURITY_IMPLEMENTATION.md
- PRODUCTION_READINESS_REVIEW.md
- QUICK_START.md

These documents describe operational setup and engineering practices.

## Documentation

Important documentation files:

PRODUCT_REQUIREMENTS.md  
SYSTEM_ARCHITECTURE.md  
AGENTS.md  
CLAUDE.md  

Agents configuration:

.claude/agents/