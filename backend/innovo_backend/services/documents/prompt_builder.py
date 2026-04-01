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
        company_name: str = "Unknown Company",
        company_profile: Optional[Dict[str, Any]] = None,
        website_clean_text: Optional[str] = None,
        transcript_clean: Optional[str] = None,
        company_id: Optional[int] = None,
    ):
        self._context = context

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

    def _get_company_name(self) -> str:
        if self._context and self._context.company_profile_json:
            profile = self._context.company_profile_json
            if isinstance(profile, dict):
                return profile.get("company_name") or "Unknown Company"
        return self._company_name

    def _get_company_profile(self) -> Optional[Dict[str, Any]]:
        if self._context and self._context.company_profile_json:
            return self._context.company_profile_json if isinstance(self._context.company_profile_json, dict) else None
        return self._company_profile

    def _get_website_clean_text(self) -> Optional[str]:
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
            return self._context.funding_rules_json if isinstance(self._context.funding_rules_json, dict) else None
        return self._funding_rules

    def _get_style_profile(self) -> Optional[Dict[str, Any]]:
        if self._context and self._context.style_profile_json:
            return self._context.style_profile_json if isinstance(self._context.style_profile_json, dict) else None
        return self._style_profile

    def _get_retrieved_examples(self) -> List[dict]:
        if not self._context or not self._context.retrieved_examples_json:
            return []
        data = self._context.retrieved_examples_json
        if isinstance(data, dict):
            chunks = data.get("examples") or []
            return chunks if isinstance(chunks, list) else []
        if isinstance(data, list):
            return data
        return []

    def _get_guideline_chunks(self) -> List[dict]:
        if not self._context or not self._context.retrieved_examples_json:
            return []
        data = self._context.retrieved_examples_json
        if isinstance(data, dict):
            chunks = data.get("guidelines") or []
            return chunks if isinstance(chunks, list) else []
        return []

    def _get_domain_chunks(self) -> List[dict]:
        if not self._context or not self._context.retrieved_examples_json:
            return []
        data = self._context.retrieved_examples_json
        if isinstance(data, dict):
            chunks = data.get("domain") or []
            return chunks if isinstance(chunks, list) else []
        return []

    @staticmethod
    def _format_company_context(
        company_profile: Optional[Dict[str, Any]],
        company_name: str,
        website_clean_text: Optional[str] = None,
        transcript_clean: Optional[str] = None,
        company_id: Optional[int] = None,
    ) -> str:
        context_parts = []

        if company_profile:
            context_parts.append("=== PRIMÄRE FAKTENQUELLE (Strukturiertes Firmenprofil) ===")
            context_parts.append(f"Firmenname: {company_name}")

            if company_profile.get("industry"):
                context_parts.append(f"Branche: {company_profile['industry']}")
            if company_profile.get("products_or_services"):
                products = company_profile["products_or_services"]
                if isinstance(products, list) and products:
                    context_parts.append(f"Produkte/Dienstleistungen: {', '.join(products)}")
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

        if website_clean_text or transcript_clean:
            context_parts.append("\n=== KONTEXTUELLE ERGÄNZUNG ===")
            MAX_TEXT_LENGTH = 30000

            if website_clean_text:
                if len(website_clean_text) > MAX_TEXT_LENGTH:
                    first_part = website_clean_text[:int(MAX_TEXT_LENGTH * 0.6)]
                    last_part = website_clean_text[-int(MAX_TEXT_LENGTH * 0.4):]
                    website_clean_text = f"{first_part}\n\n[... Inhalt gekürzt ...]\n\n{last_part}"
                context_parts.append(f"Website-Inhalt (bereinigt):\n{website_clean_text}")

            if transcript_clean:
                if len(transcript_clean) > MAX_TEXT_LENGTH:
                    first_part = transcript_clean[:int(MAX_TEXT_LENGTH * 0.6)]
                    last_part = transcript_clean[-int(MAX_TEXT_LENGTH * 0.4):]
                    transcript_clean = f"{first_part}\n\n[... Inhalt gekürzt ...]\n\n{last_part}"
                context_parts.append(f"Besprechungsprotokoll (bereinigt):\n{transcript_clean}")

        return "\n".join(context_parts)

    def build_generation_prompt(self, sections: List[dict]) -> str:
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

        headings_list = []
        section_ids = []
        for section in sections:
            if section.get("type") == "milestone_table":
                continue
            section_id = section.get("id", "")
            section_title = section.get("title", "")
            clean_title = re.sub(r"^[\d.]+\.\s*", "", section_title)
            headings_list.append(f"{section_id}. {clean_title}")
            section_ids.append(section_id)

        headings_text = "\n".join(headings_list)

        rules_section = ""
        if funding_program_rules:
            rules_parts = []
            for key, label in [
                ("eligibility_rules", "Berechtigungskriterien"),
                ("required_sections", "Erforderliche Abschnitte"),
                ("forbidden_content", "Verbotene Inhalte"),
                ("formal_requirements", "Formale Anforderungen"),
                ("evaluation_criteria", "Bewertungskriterien"),
                ("funding_limits", "Fördergrenzen"),
                ("deadlines", "Fristen"),
                ("important_notes", "Wichtige Hinweise"),
            ]:
                items = funding_program_rules.get(key)
                if items:
                    rules_parts.append(f"{label}:\n" + "\n".join(f"- {r}" for r in items))

            if rules_parts:
                rules_section = "=== 1. FÖRDERRICHTLINIEN UND REGELN ===\n\n" + "\n\n".join(rules_parts) + "\n\n"

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

        company_context = self._format_company_context(
            company_profile=company_profile,
            company_name=company_name,
            website_clean_text=website_clean_text,
            transcript_clean=transcript_clean,
            company_id=company_id,
        )
        company_section = f"=== 2. FIRMENINFORMATIONEN (FAKTENQUELLE) ===\n\n{company_context}\n\n"

        style_section = ""
        if style_profile:
            style_parts = []
            for key, label in [
                ("structure_patterns", "Strukturmuster"),
                ("tone_characteristics", "Ton und Charakteristik"),
                ("writing_style_rules", "Schreibstil-Regeln"),
                ("storytelling_flow", "Erzählstruktur und Flow"),
                ("common_section_headings", "Typische Abschnittsüberschriften"),
            ]:
                items = style_profile.get(key)
                if isinstance(items, list) and items:
                    style_parts.append(f"{label}:\n" + "\n".join(f"- {p}" for p in items))

            if style_parts:
                style_section = "=== 3. STIL-LEITFADEN ===\n\n" + "\n\n".join(style_parts) + "\n\n"
                style_section += "WICHTIG: Folgen Sie diesen Stilrichtlinien STRENG bei der Generierung.\n"
                style_section += "Passen Sie Ton, Struktur, Satzlänge und Erzählweise an diese Vorgaben an.\n\n"
        else:
            style_section = "=== 3. STIL-LEITFADEN ===\n\n"
            style_section += "- Verwenden Sie formelle Fördermittel-/Geschäftssprache\n"
            style_section += "- Professioneller, überzeugender Ton\n"
            style_section += "- Klare Absatzstruktur\n\n"

        next_num = 4

        domain_section = ""
        if domain_chunks:
            domain_texts = [c.get("chunk_text", "").strip() for c in domain_chunks if c.get("chunk_text")]
            if domain_texts:
                domain_section = (
                    f"=== {next_num}. DOMÄNENWISSEN (Technischer Hintergrund) ===\n\n"
                    + "\n\n---\n\n".join(domain_texts)
                    + "\n\nHINWEIS: Verwenden Sie dieses Domänenwissen als inhaltlichen Hintergrund.\n\n"
                )
                next_num += 1

        examples_section = ""
        if retrieved_examples:
            example_parts = [ex.get("chunk_text", "").strip() for ex in retrieved_examples if ex.get("chunk_text")]
            if example_parts:
                examples_section = (
                    f"=== {next_num}. REFERENZBEISPIELE (Auszüge aus ähnlichen Förderanträgen) ===\n\n"
                    + "\n\n---\n\n".join(example_parts)
                    + "\n\nHINWEIS: Die obigen Beispiele dienen als stilistischer Referenzrahmen. "
                    "Verwenden Sie KEINE konkreten Daten oder Fakten daraus.\n\n"
                )
                next_num += 1

        task_section = f"""=== {next_num}. GENERIERUNGSAUFGABE ===

Zu generierende Abschnitte:
{headings_text}

AUFGABE:
Generieren Sie für jeden oben genannten Abschnitt detaillierte, professionelle Inhalte.

WICHTIGE RANDBEDINGUNGEN:
- Folgen Sie den Förderrichtlinien STRENG
- Erfinden Sie KEINE Daten - verwenden Sie NUR die bereitgestellten Firmeninformationen
- Folgen Sie dem Stil-Leitfaden STRENG
- Schreiben Sie AUSSCHLIESSLICH auf Deutsch
- Verwenden Sie NUR Absätze (keine Aufzählungspunkte)
- Fügen Sie KEINE Platzhalter, Fragen oder Haftungsausschlüsse ein

"""

        prompt = f"""Sie sind ein Expertenberater, der bei der Erstellung einer "Vorhabensbeschreibung" für einen Förderantrag hilft.

{rules_section}{company_section}{style_section}{domain_section}{examples_section}{task_section}

AUSGABEFORMAT:
Geben Sie NUR ein gültiges JSON-Objekt mit dieser exakten Struktur zurück:
{{
  "{section_ids[0] if section_ids else 'section_id'}": "Generierter Absatztext...",
  "weitere_abschnitt_id": "Weiterer Absatztext..."
}}

Die Schlüssel MÜSSEN exakt mit den Abschnitts-IDs übereinstimmen (z.B. "0", "1", "1.1", "2.3", etc.).
Jeder Wert MUSS ein String sein (kein JSON, keine Arrays, keine verschachtelten Objekte).
"""
        return prompt
