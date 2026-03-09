# Project Agents

This repository uses specialized agents for different areas of the system.

Each agent has its own rule set located in:

.claude/agents/

Agents should be invoked when a task falls within their responsibility area.

---

## Backend Agent

Location: `.claude/agents/backend.md`

Responsible for:

- FastAPI routers
- database queries
- SQLAlchemy models
- service-layer logic
- database migrations
- API performance improvements

Focus:

- maintain API stability
- keep routers thin
- move business logic into services

---

## Frontend Agent

Location: `.claude/agents/frontend.md`

Responsible for:

- React components
- UI improvements
- API integration
- frontend performance
- user experience improvements

Focus:

- maintain existing UI patterns
- avoid unnecessary re-renders
- keep components maintainable

---

## LLM Pipeline Agent

Location: `.claude/agents/llm_pipeline.md`

Responsible for:

- prompt architecture
- token optimization
- generation pipeline
- OpenAI API usage

Focus:

- reducing token usage
- improving generation reliability
- enforcing structured outputs

---

## Security Agent

Location: `.claude/agents/security.md`

Responsible for:

- authentication
- input validation
- SSRF prevention
- prompt injection mitigation
- rate limiting

Focus:

- protecting user data
- preventing API abuse