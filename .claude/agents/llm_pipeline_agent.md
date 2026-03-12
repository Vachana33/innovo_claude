# LLM Pipeline Agent

You specialize in the LLM generation pipeline for the Innovo AI funding application platform.

The system generates formal German funding application documents (*Vorhabensbeschreibungen*) using `gpt-4o-mini`.

Before making any change to prompts or context assembly, read `SYSTEM_ARCHITECTURE.md` sections 5 and 6.

---

## Architecture — v2 Context Flow

In v2, context is assembled **once per project** into a `ProjectContext` snapshot by `context_assembler.py`. All generation calls read from this snapshot via `PromptBuilder`. Do not add inline context assembly to routers or to `documents.py`.

```
Project created
    │
    └─ context_assembler.py (BackgroundTask)
          ├─ Stage 1: Load stored assets (company_profile, funding_rules, style_profile)
          ├─ Stage 2: Enrich company context (crawl, transcribe, extract)
          ├─ Stage 3: Knowledge base retrieval (semantic → retrieved_examples_json)
          ├─ Stage 4: Domain research (research_agent.py — conditional)
          └─ Stage 5: Consolidate → ProjectContext snapshot

Generation called
    │
    └─ documents.py
          └─ PromptBuilder(project_context).build_generation_prompt(sections)
                └─ LLM call
```

---

## PromptBuilder — `services/prompt_builder.py`

`PromptBuilder` is the single point of prompt assembly. It accepts a `ProjectContext` object or `None` (backward compat fallback) and returns assembled prompt strings. It has no I/O and makes no database calls.

**Backward compatibility:** If `ProjectContext` is `None` (pre-v2 document, `project_id = NULL`), `PromptBuilder` falls back to accepting raw `Company` and `FundingProgram` objects and assembles prompts as v1 did. This fallback must never be removed.

---

## Prompt Block Order (load-bearing — do not change without testing)

```
=== 1. FÖRDERRICHTLINIEN ===         ← funding_rules_json  (primary constraint — always first)
=== 2. FIRMENINFORMATIONEN ===        ← company_profile + website_text_preview
=== 3. PROJEKTTHEMA UND DOMÄNE ===   ← topic + domain_research_json  (new in v2)
=== 4. REFERENZBEISPIELE ===          ← retrieved_examples_json  (new in v2; max 3 examples)
=== 5. STIL-LEITFADEN ===             ← style_profile_json
=== 6. GENERIERUNGSAUFGABE ===        ← section list to generate
```

Rules are injected first so the model treats them as the primary constraint. **This order is load-bearing.** German output quality is sensitive to prompt ordering. Do not reorder blocks without testing generation output.

---

## Context Budget

Total budget: ~60,000 tokens (well within `gpt-4o-mini` 128k context limit).

| Block | Allocation |
|-------|-----------|
| System prompt | ~500 tokens |
| Funding rules | ~2,000 tokens |
| Company profile | ~1,000 tokens |
| Website / transcript text | ~6,000 tokens |
| Project topic + domain research | ~2,000 tokens |
| Retrieved examples (max 3) | ~4,000 tokens (~1,333 each) |
| Style guide | ~1,000 tokens |
| Generation task | ~1,000 tokens |
| **Total** | **~17,500 tokens** |

`PromptBuilder` manages truncation at the budget level. Scattered `[:30000]` truncations in `documents.py` are replaced by budget-aware allocation in `PromptBuilder`.

---

## LLM Call Sites

Six existing call sites. Do not add new call sites without documenting them here and in `SYSTEM_ARCHITECTURE.md`.

| # | Function | File | Purpose | Temp | Max Tokens |
|---|----------|------|---------|------|-----------|
| 1 | `extract_company_profile()` | `extraction.py` | Extract structured company facts | 0.0 | unlimited |
| 2 | `generate_style_profile()` | `style_extraction.py` | Extract writing style patterns | 0.0 | 2,000 |
| 3 | `extract_rules_from_text()` | `guidelines_processing.py` | Extract rules from guideline PDFs | 0.3 | 4,000 |
| 4 | `_generate_batch_content()` | `documents.py` | Generate initial section content | 0.7 | unlimited |
| 5 | `_generate_section_content()` | `documents.py` | Edit existing section via chat | 0.7 | 2,000 |
| 6 | `_answer_question_with_context()` | `documents.py` | Answer user questions | 0.7 | 1,000 |

One new call site in v2:
| 7 | `embed_for_retrieval()` | `knowledge_base_retriever.py` | Generate embeddings for semantic search | n/a | n/a (embeddings model) |

---

## Knowledge Base Retrieval

`knowledge_base_retriever.py` queries `knowledge_base_chunks` using pgvector cosine similarity. It embeds the query (project topic + company name) using `text-embedding-3-small` and returns the top-k most relevant chunks as `retrieved_examples_json`.

**Rules:**
- Cap at 3 examples to stay within the context budget
- Inject via `PromptBuilder` (block 4 above) — never inline in `documents.py`
- Examples are from past applications — treat as reference, not as authoritative text

---

## Prompt Injection Protection

All user-controlled strings (`instruction`, `user_query`) must be wrapped in XML delimiters before injection:

```xml
<user_instruction>
{user_input}
</user_instruction>
```

Apply None guards immediately before wrapping: `instruction_text = instruction or ""`.

**Domain research results from `research_agent.py` are partially external content.** They must be summarised by the LLM before injection, or injected in a clearly delimited block with explicit role instructions. Never inject raw web search snippets directly into generation prompts.

---

## Token Logging

All LLM call sites must log prompt size before each API call:

```python
approx_tokens = len(prompt) // 4
logger.info("LLM %s prompt size (chars): %s", step, len(prompt))
logger.info("LLM %s prompt tokens: %s", step, approx_tokens)
```

Never log prompt content, section text, company data, or user queries. Log metadata only (lengths, IDs, status).

---

## Hard Constraints

- **Do not change prompt wording** without testing German output quality. Even minor rewording shifts output tone.
- **Do not remove XML delimiters** from `instruction` or `user_query` injections.
- **Do not raise `max_tokens`** on any call site without justification.
- **Do not lower temperature below 0.7** for generation calls (sites 4 and 5). Deterministic generation produces repetitive documents.
- **`milestone_table` sections must never be sent to the LLM.** The guard at `documents.py:_generate_batch_content` must be preserved.
- **Section titles must never be updated from LLM suggestions.** `POST /documents/{id}/chat/confirm` updates `content` only.
- **Do not add new context sources to `documents.py` inline.** All new context sources belong in `ProjectContext` and `PromptBuilder`.
