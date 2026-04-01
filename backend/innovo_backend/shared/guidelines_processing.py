"""
Guidelines processing for funding programs.
Extracts structured rules from guideline documents using LLM.
"""
import os
import logging
import hashlib
import re
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from openai import OpenAI
from innovo_backend.shared.observability import log_openai_call
from innovo_backend.shared.models import FundingProgramDocument, FundingProgramGuidelinesSummary, File as FileModel
from innovo_backend.shared.processing_cache import get_cached_document_text

logger = logging.getLogger(__name__)


def compute_combined_hash(content_hashes: List[str]) -> str:
    sorted_hashes = sorted(content_hashes)
    combined = "|".join(sorted_hashes)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def clean_extracted_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)

    lines = text.split("\n")
    seen_headers: set = set()
    cleaned_lines = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            cleaned_lines.append("")
            continue

        is_likely_header = (
            len(line_stripped) < 100
            and (line_stripped.isupper() or line_stripped.istitle())
            and line_stripped not in seen_headers
        )

        if is_likely_header:
            seen_headers.add(line_stripped)
            cleaned_lines.append(line)
        elif line_stripped.lower() not in [h.lower() for h in seen_headers]:
            cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_rules_from_text(text: str) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    client = OpenAI(api_key=api_key)

    prompt = f"""Sie sind ein Experte für Förderrichtlinien-Analyse. Analysieren Sie den folgenden Text aus Förderrichtlinien-Dokumenten und extrahieren Sie strukturierte Regeln.

RICHTLINIEN-TEXT:
{text[:50000]}

AUFGABE:
Extrahieren Sie alle relevanten Regeln und Anforderungen und strukturieren Sie sie in folgendem JSON-Format:

{{
  "eligibility_rules": ["Liste von Berechtigungskriterien"],
  "funding_limits": ["Liste von Fördergrenzen und -höhen"],
  "required_sections": ["Liste von erforderlichen Abschnitten im Antrag"],
  "forbidden_content": ["Liste von verbotenen Inhalten"],
  "formal_requirements": ["Liste von formalen Anforderungen"],
  "evaluation_criteria": ["Liste von Bewertungskriterien"],
  "deadlines": ["Liste von Fristen und Terminen"],
  "important_notes": ["Liste von wichtigen Hinweisen"]
}}

WICHTIG:
- Geben Sie NUR ein gültiges JSON-Objekt zurück
- Keine zusätzlichen Erklärungen oder Kommentare
- Verwenden Sie Arrays für alle Felder
- Wenn keine Informationen zu einem Feld vorhanden sind, verwenden Sie ein leeres Array []

JSON:"""

    approx_tokens = len(prompt) // 4
    logger.info("LLM guideline extraction prompt size (chars): %s", len(prompt))
    logger.info("LLM guideline extraction tokens: %s", approx_tokens)
    try:
        with log_openai_call(logger, "extract_rules_from_text", __file__, "gpt-4o-mini") as openai_ctx:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Sie sind ein Experte für die Analyse von Förderrichtlinien. Sie extrahieren strukturierte Regeln aus Dokumenten.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
                timeout=120.0,
            )
            openai_ctx["response"] = response

        result_text = response.choices[0].message.content.strip()

        json_match = re.search(r"\{[\s\S]*\}", result_text)
        if json_match:
            result_text = json_match.group(0)

        rules = json.loads(result_text)

        required_fields = [
            "eligibility_rules",
            "funding_limits",
            "required_sections",
            "forbidden_content",
            "formal_requirements",
            "evaluation_criteria",
            "deadlines",
            "important_notes",
        ]

        for field in required_fields:
            if field not in rules:
                rules[field] = []
            elif not isinstance(rules[field], list):
                rules[field] = [str(rules[field])]

        logger.info(
            "Extracted rules with %s total rules",
            sum(len(v) for v in rules.values() if isinstance(v, list)),
        )
        return rules

    except Exception as e:
        logger.error("Error extracting rules from text: %s", str(e))
        raise


def process_guidelines_for_funding_program(
    funding_program_id: int,
    db: Session,
) -> Optional[FundingProgramGuidelinesSummary]:
    guideline_docs = (
        db.query(FundingProgramDocument)
        .filter(
            FundingProgramDocument.funding_program_id == funding_program_id,
            FundingProgramDocument.category == "guidelines",
        )
        .all()
    )

    if not guideline_docs:
        logger.info("No guideline documents found for funding_program_id=%s", funding_program_id)
        return None

    file_hashes: List[str] = []
    extracted_texts: List[str] = []

    for doc in guideline_docs:
        file_record = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
        if not file_record:
            logger.warning("File record not found for document %s", doc.id)
            continue

        file_hashes.append(file_record.content_hash)

        text = get_cached_document_text(db, file_record.content_hash)
        if text:
            extracted_texts.append(text)
        else:
            logger.warning(
                "No extracted text found for file %s (hash: %s)",
                file_record.id,
                file_record.content_hash,
            )

    if not extracted_texts:
        logger.warning("No extracted text available for funding_program_id=%s", funding_program_id)
        return None

    combined_text = "\n\n".join(extracted_texts)
    cleaned_text = clean_extracted_text(combined_text)
    combined_hash = compute_combined_hash(file_hashes)

    existing_summary = (
        db.query(FundingProgramGuidelinesSummary)
        .filter(FundingProgramGuidelinesSummary.funding_program_id == funding_program_id)
        .first()
    )

    if existing_summary and existing_summary.source_file_hash == combined_hash:
        logger.info(
            "Guidelines summary unchanged for funding_program_id=%s (hash: %s...)",
            funding_program_id,
            combined_hash[:16],
        )
        return existing_summary

    logger.info(
        "Regenerating guidelines summary for funding_program_id=%s (hash: %s...)",
        funding_program_id,
        combined_hash[:16],
    )

    rules_json = extract_rules_from_text(cleaned_text)

    if existing_summary:
        existing_summary.rules_json = rules_json
        existing_summary.source_file_hash = combined_hash
        db.commit()
        db.refresh(existing_summary)
        logger.info("Updated guidelines summary for funding_program_id=%s", funding_program_id)
        return existing_summary
    else:
        new_summary = FundingProgramGuidelinesSummary(
            funding_program_id=funding_program_id,
            rules_json=rules_json,
            source_file_hash=combined_hash,
        )
        db.add(new_summary)
        db.commit()
        db.refresh(new_summary)
        logger.info("Created new guidelines summary for funding_program_id=%s", funding_program_id)
        return new_summary
