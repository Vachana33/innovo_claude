"""
PromptBuilder — pure prompt assembly for Vorhabensbeschreibung generation.

No I/O, no database calls, no logging, no API calls.
Returns prompt strings; caller is responsible for logging and API calls.
"""
import re
from typing import Any, Dict, List, Optional


class PromptBuilder:
    """
    Assembles LLM prompts from either a ProjectContext (v2 path) or
    direct data (v1 fallback path).

    Constructor:
        v2:  PromptBuilder(context=project_context)
        v1 (ORM):   PromptBuilder(company=company_obj, funding_rules=rules, style_profile=style)
        v1 (raw):   PromptBuilder(company_name=..., company_profile=..., funding_rules=..., style_profile=...)
    """

    def __init__(
        self,
        context=None,
        company=None,
        funding_rules: Optional[Dict[str, Any]] = None,
        style_profile: Optional[Dict[str, Any]] = None,
        # v1 raw-data form (used when called from helper functions that have extracted data)
        company_name: str = "Unknown Company",
        company_profile: Optional[Dict[str, Any]] = None,
        website_clean_text: Optional[str] = None,
        transcript_clean: Optional[str] = None,
        company_id: Optional[int] = None,
    ):
        self._context = context

        # v1 path: resolve from Company ORM or raw data kwargs
        if company is not None:
            self._company_name = company.name or "Unknown Company"
            self._company_profile = company.company_profile
            self._website_clean_text = getattr(company, "website_clean_text", None) or None
            self._transcript_clean = getattr(company, "transcript_clean", None) or None
            self._company_id = company.id
        else:
            self._company_name = company_name
            self._company_profile = company_profile
            self._website_clean_text = website_clean_text
            self._transcript_clean = transcript_clean
            self._company_id = company_id

        self._funding_rules = funding_rules
        self._style_profile = style_profile

    # ── Private data resolution ──────────────────────────────────────────────

    def _get_company_name(self) -> str:
        if self._context and self._context.company_profile_json:
            return self._context.company_profile_json.get("company_name") or "Unknown Company"
        return self._company_name

    def _get_company_profile(self) -> Optional[Dict[str, Any]]:
        if self._context and self._context.company_profile_json:
            return self._context.company_profile_json
        return self._company_profile

    def _get_website_clean_text(self) -> Optional[str]:
        # ProjectContext does not store raw cleaned texts
        if self._context:
            return None
        return self._website_clean_text

    def _get_transcript_clean(self) -> Optional[str]:
        if self._context:
            return None
        return self._transcript_clean

    def _get_company_id(self) -> Optional[int]:
        if self._context:
            return None
        return self._company_id

    def _get_funding_rules(self) -> Optional[Dict[str, Any]]:
        if self._context and self._context.funding_rules_json:
            return self._context.funding_rules_json
        return self._funding_rules

    def _get_style_profile(self) -> Optional[Dict[str, Any]]:
        if self._context and self._context.style_profile_json:
            return self._context.style_profile_json
        return self._style_profile

    def _get_retrieved_examples(self) -> List[dict]:
        """
        Return example KB chunks (old Vorhabensbeschreibung passages).

        Handles both formats:
          - New structured format: retrieved_examples_json is a dict with key "examples"
          - Legacy flat format:    retrieved_examples_json is a list (all treated as examples)
        """
        if not self._context or not self._context.retrieved_examples_json:
            return []
        data = self._context.retrieved_examples_json
        if isinstance(data, dict):
            chunks = data.get("examples") or []
            return chunks if isinstance(chunks, list) else []
        if isinstance(data, list):
            return data  # legacy flat list
        return []

    def _get_guideline_chunks(self) -> List[dict]:
        """Return KB guideline chunks (raw passages from funding program documents)."""
        if not self._context or not self._context.retrieved_examples_json:
            return []
        data = self._context.retrieved_examples_json
        if isinstance(data, dict):
            chunks = data.get("guidelines") or []
            return chunks if isinstance(chunks, list) else []
        return []

    def _get_domain_chunks(self) -> List[dict]:
        """Return KB domain chunks (general technical / domain knowledge passages)."""
        if not self._context or not self._context.retrieved_examples_json:
            return []
        data = self._context.retrieved_examples_json
        if isinstance(data, dict):
            chunks = data.get("domain") or []
            return chunks if isinstance(chunks, list) else []
        return []

    # ── Private formatting helper ────────────────────────────────────────────

    @staticmethod
    def _format_company_context(
        company_profile: Optional[Dict[str, Any]],
        company_name: str,
        website_clean_text: Optional[str] = None,
        transcript_clean: Optional[str] = None,
        company_id: Optional[int] = None,
    ) -> str:
        """
        Format company context for LLM prompts.
        Logic verbatim from _format_company_context_for_prompt in documents.py.
        Logging calls omitted — PromptBuilder is pure (no logging).
        """
        context_parts = []

        # PRIMARY SOURCE: Structured company profile
        if company_profile:
            context_parts.append("=== PRIMÄRE FAKTENQUELLE (Strukturiertes Firmenprofil) ===")
            context_parts.append(f"Firmenname: {company_name}")

            if company_profile.get("industry"):
                context_parts.append(f"Branche: {company_profile['industry']}")

            if company_profile.get("products_or_services"):
                products = company_profile["products_or_services"]
                if isinstance(products, list) and products:
                    products_str = ", ".join(products)
                    context_parts.append(f"Produkte/Dienstleistungen: {products_str}")
                elif isinstance(products, str):
                    context_parts.append(f"Produkte/Dienstleistungen: {products}")

            if company_profile.get("business_model"):
                context_parts.append(f"Geschäftsmodell: {company_profile['business_model']}")

            if company_profile.get("market"):
                context_parts.append(f"Zielmarkt: {company_profile['market']}")

            if company_profile.get("innovation_focus"):
                context_parts.append(f"Innovationsschwerpunkt: {company_profile['innovation_focus']}")

            if company_profile.get("company_size"):
                context_parts.append(f"Unternehmensgröße: {company_profile['company_size']}")

            if company_profile.get("location"):
                context_parts.append(f"Standort: {company_profile['location']}")
        else:
            context_parts.append("=== PRIMÄRE FAKTENQUELLE ===")
            context_parts.append(f"Firmenname: {company_name}")

        # CONTEXTUAL ENRICHMENT: Cleaned texts
        if website_clean_text or transcript_clean:
            context_parts.append("\n=== KONTEXTUELLE ERGÄNZUNG ===")

            if website_clean_text:
                MAX_TEXT_LENGTH = 30000
                if len(website_clean_text) > MAX_TEXT_LENGTH:
                    first_part = website_clean_text[:int(MAX_TEXT_LENGTH * 0.6)]
                    last_part = website_clean_text[-int(MAX_TEXT_LENGTH * 0.4):]
                    website_clean_text = f"{first_part}\n\n[... Inhalt gekürzt ...]\n\n{last_part}"
                context_parts.append(f"Website-Inhalt (bereinigt):\n{website_clean_text}")

            if transcript_clean:
                MAX_TEXT_LENGTH = 30000
                if len(transcript_clean) > MAX_TEXT_LENGTH:
                    first_part = transcript_clean[:int(MAX_TEXT_LENGTH * 0.6)]
                    last_part = transcript_clean[-int(MAX_TEXT_LENGTH * 0.4):]
                    transcript_clean = f"{first_part}\n\n[... Inhalt gekürzt ...]\n\n{last_part}"
                context_parts.append(f"Besprechungsprotokoll (bereinigt):\n{transcript_clean}")

        return "\n".join(context_parts)

    # ── Public build methods ─────────────────────────────────────────────────

    def build_generation_prompt(self, sections: List[dict]) -> str:
        """
        Assemble the initial generation prompt.
        Prompt wording copied verbatim from _generate_batch_content in documents.py.
        """
        funding_program_rules = self._get_funding_rules()
        company_name = self._get_company_name()
        company_profile = self._get_company_profile()
        website_clean_text = self._get_website_clean_text()
        transcript_clean = self._get_transcript_clean()
        company_id = self._get_company_id()
        style_profile = self._get_style_profile()
        retrieved_examples = self._get_retrieved_examples()
        guideline_chunks = self._get_guideline_chunks()
        domain_chunks = self._get_domain_chunks()

        # Build headings list for this batch (exclude milestone tables)
        headings_list = []
        section_ids = []
        for section in sections:
            # Skip milestone tables - they should not be AI-generated
            if section.get('type') == 'milestone_table':
                continue
            section_id = section.get('id', '')
            section_title = section.get('title', '')
            # Remove numbering prefix from title
            clean_title = re.sub(r'^[\d.]+\.\s*', '', section_title)
            headings_list.append(f"{section_id}. {clean_title}")
            section_ids.append(section_id)

        headings_text = "\n".join(headings_list)

        # IMPORTANT: This prompt is for INITIAL CONTENT GENERATION only.
        # It assumes empty sections and focuses on creation.
        # Do NOT reuse this prompt for chat-based editing.
        # For editing existing content, use build_edit_prompt() instead.

        # ============================================
        # PROMPT STRUCTURE: Rules → Company → Style → Task
        # ============================================

        # 1. RULES SECTION (from funding program guidelines)
        rules_section = ""
        if funding_program_rules:
            rules_parts = []
            if funding_program_rules.get("eligibility_rules"):
                rules_parts.append("Berechtigungskriterien:\n" + "\n".join(f"- {r}" for r in funding_program_rules["eligibility_rules"]))
            if funding_program_rules.get("required_sections"):
                rules_parts.append("Erforderliche Abschnitte:\n" + "\n".join(f"- {r}" for r in funding_program_rules["required_sections"]))
            if funding_program_rules.get("forbidden_content"):
                rules_parts.append("Verbotene Inhalte:\n" + "\n".join(f"- {r}" for r in funding_program_rules["forbidden_content"]))
            if funding_program_rules.get("formal_requirements"):
                rules_parts.append("Formale Anforderungen:\n" + "\n".join(f"- {r}" for r in funding_program_rules["formal_requirements"]))
            if funding_program_rules.get("evaluation_criteria"):
                rules_parts.append("Bewertungskriterien:\n" + "\n".join(f"- {r}" for r in funding_program_rules["evaluation_criteria"]))
            if funding_program_rules.get("funding_limits"):
                rules_parts.append("Fördergrenzen:\n" + "\n".join(f"- {r}" for r in funding_program_rules["funding_limits"]))
            if funding_program_rules.get("deadlines"):
                rules_parts.append("Fristen:\n" + "\n".join(f"- {r}" for r in funding_program_rules["deadlines"]))
            if funding_program_rules.get("important_notes"):
                rules_parts.append("Wichtige Hinweise:\n" + "\n".join(f"- {r}" for r in funding_program_rules["important_notes"]))

            if rules_parts:
                rules_section = "=== 1. FÖRDERRICHTLINIEN UND REGELN ===\n\n" + "\n\n".join(rules_parts) + "\n\n"

        # Append KB guideline passages to section 1 as supplementary raw excerpts.
        # These are semantically matched passages from uploaded guideline documents;
        # they complement the structured summary above with verbatim program language.
        if guideline_chunks:
            guideline_texts = [c.get("chunk_text", "").strip() for c in guideline_chunks if c.get("chunk_text")]
            if guideline_texts:
                if not rules_section:
                    rules_section = "=== 1. FÖRDERRICHTLINIEN UND REGELN ===\n\n"
                rules_section += (
                    "--- Relevante Auszüge aus Förderrichtlinien ---\n\n"
                    + "\n\n---\n\n".join(guideline_texts)
                    + "\n\n"
                )

        # 2. COMPANY SOURCE SECTION (primary: company_profile, enrichment: cleaned texts)
        company_context = self._format_company_context(
            company_profile=company_profile,
            company_name=company_name,
            website_clean_text=website_clean_text,
            transcript_clean=transcript_clean,
            company_id=company_id,
        )
        company_section = f"=== 2. FIRMENINFORMATIONEN (FAKTENQUELLE) ===\n\n{company_context}\n\n"

        # 3. STYLE GUIDE SECTION (from AlteVorhabensbeschreibungStyleProfile)
        style_section = ""
        if style_profile:
            style_parts = []

            if style_profile.get("structure_patterns"):
                patterns = style_profile["structure_patterns"]
                if isinstance(patterns, list) and patterns:
                    style_parts.append("Strukturmuster:\n" + "\n".join(f"- {p}" for p in patterns))

            if style_profile.get("tone_characteristics"):
                tone = style_profile["tone_characteristics"]
                if isinstance(tone, list) and tone:
                    style_parts.append("Ton und Charakteristik:\n" + "\n".join(f"- {t}" for t in tone))

            if style_profile.get("writing_style_rules"):
                rules = style_profile["writing_style_rules"]
                if isinstance(rules, list) and rules:
                    style_parts.append("Schreibstil-Regeln:\n" + "\n".join(f"- {r}" for r in rules))

            if style_profile.get("storytelling_flow"):
                flow = style_profile["storytelling_flow"]
                if isinstance(flow, list) and flow:
                    style_parts.append("Erzählstruktur und Flow:\n" + "\n".join(f"- {f}" for f in flow))

            if style_profile.get("common_section_headings"):
                headings = style_profile["common_section_headings"]
                if isinstance(headings, list) and headings:
                    style_parts.append("Typische Abschnittsüberschriften:\n" + "\n".join(f"- {h}" for h in headings))

            if style_parts:
                style_section = "=== 3. STIL-LEITFADEN ===\n\n" + "\n\n".join(style_parts) + "\n\n"
                style_section += "WICHTIG: Folgen Sie diesen Stilrichtlinien STRENG bei der Generierung.\n"
                style_section += "Passen Sie Ton, Struktur, Satzlänge und Erzählweise an diese Vorgaben an.\n\n"
        else:
            style_section = "=== 3. STIL-LEITFADEN ===\n\n"
            style_section += "- Verwenden Sie formelle Fördermittel-/Geschäftssprache\n"
            style_section += "- Professioneller, überzeugender Ton\n"
            style_section += "- Klare Absatzstruktur\n\n"

        # Dynamic section numbering: 1=Rules, 2=Company, 3=Style are always present.
        # Domain and Examples are optional; Task follows whatever came last.
        next_num = 4

        # 4 (optional). DOMAIN KNOWLEDGE — general technical context from KB
        domain_section = ""
        if domain_chunks:
            domain_texts = [c.get("chunk_text", "").strip() for c in domain_chunks if c.get("chunk_text")]
            if domain_texts:
                domain_section = (
                    f"=== {next_num}. DOMÄNENWISSEN (Technischer Hintergrund) ===\n\n"
                    + "\n\n---\n\n".join(domain_texts)
                    + "\n\nHINWEIS: Verwenden Sie dieses Domänenwissen als inhaltlichen Hintergrund. "
                    "Firmenspezifische Fakten entnehmen Sie ausschließlich aus Abschnitt 2.\n\n"
                )
                next_num += 1

        # 4 or 5 (optional). REFERENCE EXAMPLES — passages from past funding applications
        examples_section = ""
        if retrieved_examples:
            example_parts = [ex.get("chunk_text", "").strip() for ex in retrieved_examples if ex.get("chunk_text")]
            if example_parts:
                joined = "\n\n---\n\n".join(example_parts)
                examples_section = (
                    f"=== {next_num}. REFERENZBEISPIELE (Auszüge aus ähnlichen Förderanträgen) ===\n\n"
                    + joined
                    + "\n\nHINWEIS: Die obigen Beispiele dienen als stilistischer Referenzrahmen. "
                    "Verwenden Sie KEINE konkreten Daten oder Fakten daraus. "
                    "Firmeninformationen entnehmen Sie ausschließlich aus Abschnitt 2.\n\n"
                )
                next_num += 1

        # GENERATION TASK — always the last numbered section
        task_section = f"""=== {next_num}. GENERIERUNGSAUFGABE ===

Zu generierende Abschnitte:
{headings_text}

AUFGABE:
Generieren Sie für jeden oben genannten Abschnitt detaillierte, professionelle Inhalte.

WICHTIGE RAND bedingungen:
- Folgen Sie den Förderrichtlinien STRENG
- Erfinden Sie KEINE Daten - verwenden Sie NUR die bereitgestellten Firmeninformationen
- Folgen Sie dem Stil-Leitfaden STRENG
- Schreiben Sie AUSSCHLIESSLICH auf Deutsch
- Verwenden Sie NUR Absätze (keine Aufzählungspunkte)
- Fügen Sie KEINE Platzhalter, Fragen oder Haftungsausschlüsse ein
- Wenn Informationen unzureichend sind, generieren Sie plausible, professionelle Inhalte basierend auf dem verfügbaren Kontext

"""

        # Build complete prompt
        prompt = f"""Sie sind ein Expertenberater, der bei der Erstellung einer "Vorhabensbeschreibung" für einen Förderantrag hilft.

{rules_section}{company_section}{style_section}{domain_section}{examples_section}{task_section}

AUSGABEFORMAT:
Geben Sie NUR ein gültiges JSON-Objekt mit dieser exakten Struktur zurück:
{{
  "{section_ids[0] if section_ids else "section_id"}": "Generierter Absatztext...",
  "{section_ids[1] if len(section_ids) > 1 else "section_id"}": "Generierter Absatztext..."
}}

Die Schlüssel MÜSSEN exakt mit den Abschnitts-IDs aus der Liste oben übereinstimmen (z.B. "0", "1", "1.1", "2.3", etc.).
Die Werte müssen reiner deutscher Text in Absatzform sein.

Geben Sie KEIN Markdown-Format, KEINE Erklärungen und KEINEN Text außerhalb des JSON-Objekts zurück. Geben Sie NUR das JSON-Objekt zurück."""

        return prompt

    def build_edit_prompt(
        self,
        section: dict,
        instruction: str,
        current_content: str,
    ) -> str:
        """
        Assemble the section edit prompt.
        Prompt wording copied verbatim from _generate_section_content in documents.py.
        """
        company_name = self._get_company_name()
        company_profile = self._get_company_profile()
        website_clean_text = self._get_website_clean_text()
        transcript_clean = self._get_transcript_clean()
        company_id = self._get_company_id()
        style_profile = self._get_style_profile()

        section_id = section.get("id", "")
        section_title = section.get("title", "")
        # Remove numbering prefix from title
        clean_title = re.sub(r'^[\d.]+\.\s*', '', section_title)

        # IMPORTANT:
        # This prompt is for EDITING existing content only.
        # Do NOT reuse this prompt for initial content generation.
        # For initial generation, use build_generation_prompt() instead.
        # This prompt assumes existing content exists and must be modified, not created.

        # Format company context using cleaned data
        company_context = self._format_company_context(
            company_profile=company_profile,
            company_name=company_name,
            website_clean_text=website_clean_text,
            transcript_clean=transcript_clean,
            company_id=company_id,
        )

        # Build style guide section from style profile
        style_guide = ""
        if style_profile:
            style_parts = []

            if style_profile.get("structure_patterns"):
                patterns = style_profile["structure_patterns"]
                if isinstance(patterns, list) and patterns:
                    style_parts.append("Strukturmuster:\n" + "\n".join(f"- {p}" for p in patterns))

            if style_profile.get("tone_characteristics"):
                tone = style_profile["tone_characteristics"]
                if isinstance(tone, list) and tone:
                    style_parts.append("Ton und Charakteristik:\n" + "\n".join(f"- {t}" for t in tone))

            if style_profile.get("writing_style_rules"):
                rules = style_profile["writing_style_rules"]
                if isinstance(rules, list) and rules:
                    style_parts.append("Schreibstil-Regeln:\n" + "\n".join(f"- {r}" for r in rules))

            if style_profile.get("storytelling_flow"):
                flow = style_profile["storytelling_flow"]
                if isinstance(flow, list) and flow:
                    style_parts.append("Erzählstruktur:\n" + "\n".join(f"- {f}" for f in flow))

            if style_parts:
                style_guide = "=== STIL-LEITFADEN ===\n\n" + "\n\n".join(style_parts) + "\n\n"
                style_guide += "WICHTIG: Folgen Sie diesen Stilrichtlinien bei der Überarbeitung.\n\n"
        else:
            style_guide = "=== STIL-LEITFADEN ===\n\n"
            style_guide += "- Verwenden Sie formelle Fördermittel-/Geschäftssprache\n"
            style_guide += "- Professioneller, überzeugender Ton\n"
            style_guide += "- Klare Absatzstruktur\n\n"

        # Build prompt with style guide
        instruction_text = instruction or ""
        prompt = f"""{style_guide}SIE SIND EIN REDAKTEUR, KEIN AUTOR.

- Der folgende Abschnitt EXISTIERT bereits.
- Ihre Aufgabe ist es, den bestehenden Text gezielt zu überarbeiten.
- Ersetzen Sie NICHT den gesamten Inhalt, außer die Benutzeranweisung verlangt dies ausdrücklich.
- Bewahren Sie Struktur, Kernaussagen und Tonalität des bestehenden Textes.

PRIMÄRE GRUNDLAGE:

- Der bestehende Abschnittstext ist die wichtigste Grundlage.
- Änderungen müssen sich auf den vorhandenen Inhalt beziehen.
- Fügen Sie neue Informationen nur hinzu, wenn sie logisch an den bestehenden Text anschließen.

Aktueller Abschnitt:
- Abschnitts-ID: {section_id}
- Titel: {clean_title}
- Aktueller Inhalt: {current_content}

Benutzeranweisung: <user_instruction>
{instruction_text}
</user_instruction>

KONTEXTNUTZUNG:

- Verwenden Sie Firmeninformationen ausschließlich zur Präzisierung oder inhaltlichen Stützung.
- Fügen Sie keine neuen Themen ein, die im bestehenden Abschnitt nicht bereits angelegt sind.
- Vermeiden Sie generische Aussagen ohne Bezug zum aktuellen Abschnitt.

Firmeninformationen (NUR ZUR STÜTZUNG):
{company_context}

UMGANG MIT ALLGEMEINEN ANWEISUNGEN:

- Bei unspezifischen Anweisungen wie „Inhalt hinzufügen", „verbessern" oder „ausbauen":
  - Erweitern Sie den bestehenden Text moderat (ca. +20–40%).
  - Vertiefen Sie bestehende Aussagen, anstatt neue Themen zu eröffnen.

- Bei spezifischen Anweisungen wie „kürzer", „präziser" oder „technischer":
  - Passen Sie den Text entsprechend an, behalten Sie aber die Kernaussagen bei.

- Bei Anweisungen wie „rewrite" oder „komplett neu":
  - Formulieren Sie den Text neu, aber behalten Sie die inhaltlichen Kernpunkte bei.
  - Erweitern Sie moderat (ca. +30–50%), nicht exzessiv.

ABSCHNITTSFOKUS:

- Der überarbeitete Text muss inhaltlich eindeutig zum Titel des Abschnitts passen.
- Fügen Sie keine Themen hinzu, die zu anderen Abschnitten gehören.
- Ändern Sie NICHT den Titel oder die Struktur des Abschnitts.

STIL UND SPRACHE:

- Schreiben Sie ausschließlich auf Deutsch.
- Verwenden Sie einen sachlichen, formellen Fördermittel-Stil.
- Schreiben Sie in zusammenhängenden Absätzen (keine Aufzählungen).
- Keine Meta-Kommentare, keine Hinweise auf KI, keine Platzhalter.
- Stellen Sie KEINE Fragen.
- Fügen Sie KEINE Zitate oder Haftungsausschlüsse ein.
- Erwähnen Sie KEINE vorherigen Versionen oder Änderungen.

WICHTIG:

- Ändern Sie NICHT den Abschnittstitel.
- Fügen Sie KEINE neuen Abschnitte hinzu.
- Der Inhalt muss mit den Firmeninformationen übereinstimmen.
- Geben Sie NUR den überarbeiteten Absatztext zurück (kein JSON, kein Markdown, keine Erklärungen)."""

        return prompt

    def build_qa_prompt(
        self,
        document_text: str,
        website_summary: str,
        conversation_history: str,
        user_query: str,
    ) -> str:
        """
        Assemble the Q&A prompt.
        Prompt wording copied verbatim from _answer_question_with_context in documents.py.
        """
        company_name = self._get_company_name()

        # Build context prompt
        context_parts = []

        if document_text and document_text.strip() != "No content generated yet.":
            context_parts.append(f"Generated Document Content:\n{document_text}")

        if website_summary:
            context_parts.append(f"Company Website Summary:\n{website_summary}")

        if conversation_history:
            context_parts.append(f"Previous Conversation:\n{conversation_history}")

        context_text = "\n\n".join(context_parts)

        user_query_text = user_query or ""
        prompt = f"""Sie sind ein Expertenberater, der Fragen zu einem Förderantrag-Dokument (Vorhabensbeschreibung) beantwortet.

KONTEXT:
{context_text}

Firmenname: {company_name}

BENUTZERFRAGE: <user_instruction>
{user_query_text}
</user_instruction>

AUFGABE:
Beantworten Sie die Frage präzise und sachlich im formellen Fördermittel-Stil (Geschäftssprache).

WICHTIGE REGELN:
- Beziehen Sie sich AUSSCHLIESSLICH auf den bereitgestellten Kontext
- Wenn die Antwort nicht im Kontext enthalten ist, sagen Sie dies klar
- Verwenden Sie formelle, professionelle Sprache (Deutsch)
- Seien Sie präzise und konkret
- Keine Spekulationen oder Informationen außerhalb des Kontexts
- Keine Meta-Kommentare oder Hinweise auf KI
- Antworten Sie in zusammenhängenden Absätzen (keine Aufzählungen, außer wenn angebracht)

Geben Sie NUR die Antwort zurück, ohne zusätzliche Erklärungen oder Formatierungen."""

        return prompt
