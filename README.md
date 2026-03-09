# Demo_innovo

AI-powered funding document generation platform (Vorhabensbeschreibung). Internal use, Innovo Consulting.

---

## 1. What This System Does

- **Companies**: Create companies with optional website URL and/or meeting audio. Background task crawls website, transcribes audio (Whisper), cleans text, optionally extracts structured company profile (LLM). Results cached by file/URL hash.
- **Funding programs**: Create programs, attach guideline PDFs/DOCX. Text extracted (cached), then LLM extracts structured rules (eligibility, limits, required sections, etc.). One summary per program, keyed by combined file hash.
- **Alte Vorhabensbeschreibung**: Upload historical PDFs. Text extracted (cached); one LLM call produces a single style profile (structure, tone, rules). Profile keyed by combined source hash; used for all document generation.
- **Templates**: System templates (e.g. `wtt_v1`) and user templates define section structure. Documents are created from a template; headings fixed before generation.
- **Documents**: One document per (company, funding program, type). User confirms headings → generates content (batch LLM) → edits via chat (section-level suggest → Approve/Reject). Only approved content is saved; section titles never updated from suggestions.

---

## 2. High-Level Architecture

- **Frontend**: React 19, TypeScript, Vite, React Router 7. Per-route pages; `utils/api.ts` (JWT). Editor: document by company + funding_program + template; mode from headings_confirmed and content.
- **Backend**: FastAPI, JWT, `get_current_user`. Routers: auth, companies, funding_programs, documents, templates, alte_vorhabensbeschreibung. BackgroundTasks for preprocessing and guideline summary (single process).
- **Database**: PostgreSQL/SQLite. users, companies, funding_programs (M:N companies), documents (content_json, headings_confirmed, template_id/name, chat_history), files (content_hash, storage_path). Caches: audio_transcript, website_text, document_text. funding_program_guidelines_summary; alte_vorhabensbeschreibung_style_profile (one row).
- **Storage**: Supabase. `file_storage.py`: SHA256 → get_or_create_file; path `{type}/{hash[:2]}/{hash}.{ext}`. Backend-only.
- **LLM**: OpenAI 1.x. `_generate_batch_content` (initial sections) and `_generate_section_content` (chat edits) in documents router.

---

## 3. Core Workflows

**Company creation & preprocessing**  
Create company (website, optional audio). Background: crawl website (cache by URL hash) → transcribe (cache by file hash) → optional profile extraction → status done/failed.

**Funding program & guideline extraction**  
Attach guideline docs; on change: extract text (document_text_cache) → combined hash → LLM rules JSON → funding_program_guidelines_summary.

**Style profile generation**  
Upload PDFs → “Generate style profile”: combined_hash of sources → if new, LLM → store in alte_vorhabensbeschreibung_style_profile; else reuse.

**Document creation flow**
1. **Template selection**: GET `/documents/{company_id}/vorhabensbeschreibung?funding_program_id=...&template_id=...` creates/returns doc with template sections (content empty).
2. **Heading confirmation**: POST `/documents/{id}/confirm-headings` → headings_confirmed = true.
3. **Generate content**: POST `/documents/{id}/generate-content` → rules, company, style → _generate_batch_content → merge into content_json.
4. **Suggest → Approve/Reject**: Chat “1.3 add content” → POST `/documents/{id}/chat` → _generate_section_content → suggested_content. Approve → POST `/documents/{id}/chat/confirm` updates section content only (title unchanged); Reject → no save.

---

## 4. Document Generation Pipeline

- **Inputs**: Rules (funding_program_guidelines_summary), company (profile, website_clean_text, transcript_clean), style (alte_vorhabensbeschreibung_style_profile or none). From guidelines_processing, company preprocessing, style_extraction.
- **Generation**: Initial: `_generate_batch_content` via POST `/documents/{id}/generate-content`. Section edit: `_generate_section_content` via POST `/documents/{id}/chat`. Prompt order: rules → company → style → task.
- **Section editing**: Chat → _generate_section_content → suggested_content; confirm writes section content only (title unchanged).

---

## 5. Key Backend Modules

- **routers/documents.py**: Document CRUD, GET by company+program+template; confirm-headings; generate-content; chat + chat/confirm. Holds _generate_batch_content and _generate_section_content.
- **routers/companies.py**: Company CRUD; audio upload; company documents; process_company_background (website, audio, optional profile).
- **style_extraction.py**: compute_combined_hash; generate_style_profile(doc_texts) → LLM → style JSON.
- **guidelines_processing.py**: compute_combined_hash; extract_rules_from_text; update funding_program_guidelines_summary (cached).
- **template_resolver.py**: get_template_for_document → system by name or user by UUID; returns { sections }.
- **file_storage.py**: compute_file_hash; get_or_create_file (Supabase, hash dedupe); get_file_by_id; download.
- **processing_cache.py**: get/store audio_transcript (file hash), website_text (url hash), document_text (file hash); normalize_url, hash_url.

---

## 6. Running Locally

**Backend**
```bash
cd backend
python3 -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
# Create backend/.env (see below)
uvicorn main:app --reload --port 8000
```
Run uvicorn from `backend/` so `main:app` resolves.

**Frontend**
```bash
cd frontend
npm install
npm run dev
```
Default: http://localhost:5173. Set `VITE_API_URL=http://localhost:8000` if needed.

**Required env vars (backend)**  
`JWT_SECRET_KEY`, `OPENAI_API_KEY`. Optional: `DATABASE_URL` (default sqlite); `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_STORAGE_BUCKET` for storage; `FRONTEND_ORIGIN` for CORS.

---

## 7. Important Design Decisions

- **Loose linking**: Companies and programs M:N. Document = (company, funding_program, type).
- **Hash-based caching**: file_content_hash (transcript, doc text); url_hash (website); combined hash (guidelines, style). No TTL; invalidation by hash change.
- **Style profile**: One JSON from historical PDFs; versioned by combined_hash; not raw PDFs in prompts.
- **Section-level generation**: Headings fixed; generation fills content; enables suggest/approve per section.
- **Human-in-the-loop**: Chat suggests; user Approve to persist. Section title never updated from suggestion.

---

## 8. Common Dev Tasks

- **Add template**: Add under `app/templates/` or create user template in UI; register in `app/templates/__init__.py` for system.
- **Change prompt**: Edit `_generate_batch_content` / `_generate_section_content` in `routers/documents.py`.
- **Regenerate style**: Change PDF set or re-upload → “Generate style profile” in UI (new combined_hash → new row).
- **Debug generation**: Check OPENAI_API_KEY; company processing_status and profile; guidelines summary for program; style profile if used.
- **Reset DB**: SQLite: delete `backend/innovo.db`. PostgreSQL: drop schema or Alembic downgrade/upgrade.

---

**License**: Internal use only, Innovo Consulting.
