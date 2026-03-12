# Development Rules

These rules define how code should be modified in this repository.

They exist to ensure safe, predictable changes when AI agents or engineers work on the system.

This file focuses only on **engineering discipline**, not product logic or architecture.  
Refer to other documentation for those topics.

---

## 1. General Principles

Always prioritize:

- stability
- clarity
- incremental improvements

Do not introduce large changes unless explicitly requested.

Prefer **small, localized modifications** that preserve existing behavior.

---

## 2. Change Discipline

Before implementing any change:

1. Explain the problem.
2. Propose the solution.
3. Identify the files that must be modified.
4. Keep the change minimal and isolated.

Avoid touching unrelated files.

---

## 3. Code Organization

Follow these structural rules.

### Backend

- Keep routers thin.
- Place business logic in service/helper functions.
- Avoid adding logic directly inside route handlers.

Prefer this pattern:
router → service layer → database


### Frontend

- Keep pages focused on layout and composition.
- Move reusable logic into components or utilities.
- Avoid large components with mixed responsibilities.

---

## 4. Refactoring Rules

Refactoring is allowed only when it is **small and safe**.

Good refactors:

- extracting helper functions
- improving naming
- simplifying conditional logic
- reducing duplicated code

Avoid:

- rewriting entire modules
- reorganizing or renaming existing folder structures
- changing public interfaces

Creating new directories for new architectural layers (e.g., `backend/app/services/`) is permitted. Reorganising or renaming existing directories is not.

---

## 5. Database Safety

Database changes are high risk.

Do not:

- modify schemas
- add migrations
- remove columns

unless explicitly requested.

All existing database contracts must remain stable.

**v2 exception:** The following migrations are pre-approved as part of the v2 implementation plan and do not require additional approval: `projects` table, `project_contexts` table, `knowledge_base_documents` table, `knowledge_base_chunks` table, `project_id` FK on `documents`. All other schema changes still require explicit approval. Never modify existing migration files — add new ones only.

---

## 6. API Stability

Existing API endpoints must remain compatible.

Do not:

- change request formats
- change response shapes
- rename fields returned to the frontend

unless the change is explicitly requested.

---

## 7. AI Generation Safety

When modifying the LLM pipeline:

- avoid increasing prompt size unnecessarily
- avoid sending unused context to the model
- preserve structured outputs when possible

Do not change prompts unless the improvement is clearly justified.

---

## 8. Security Awareness

Always consider:

- prompt injection
- SSRF risks
- sensitive data exposure

Never log private company data or document contents.

---

## 9. Scope Control

Every change must remain **within the scope of the requested task**.

Do not introduce:

- unrelated refactors
- new dependencies
- architectural changes

unless explicitly approved.