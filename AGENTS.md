# Project Agents

Claude should delegate complex work across specialized agents.

## Backend Agent

Responsible for:

- FastAPI routers
- database queries
- business logic
- migrations
- performance improvements

Focus areas:
- code maintainability
- safe refactoring
- API stability

---

## Frontend Agent

Responsible for:

- React components
- UI improvements
- API integration
- UX improvements

Focus areas:
- maintain consistent UI patterns
- avoid unnecessary re-renders
- ensure safe API handling

---

## LLM Pipeline Agent

Responsible for:

- prompt design
- token optimization
- generation pipeline
- OpenAI API calls

Focus areas:

- reducing token usage
- improving output reliability
- enforcing structured outputs

---

## Security Agent

Responsible for:

- authentication
- input validation
- SSRF prevention
- prompt injection mitigation
- rate limiting

Focus areas:

- protecting user data
- preventing API abuse