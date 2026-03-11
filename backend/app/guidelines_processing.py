"""
Guidelines processing for funding programs.
Extracts structured rules from guideline documents using LLM.
"""
import os
import logging
import hashlib
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from openai import OpenAI
from app.observability import log_openai_call
from app.models import FundingProgramDocument, FundingProgramGuidelinesSummary, File as FileModel
from app.processing_cache import get_cached_document_text

logger = logging.getLogger(__name__)


def compute_combined_hash(content_hashes: List[str]) -> str:
    """
    Compute combined hash from multiple content hashes.
    Sorts hashes first to ensure consistent result regardless of order.
    """
    sorted_hashes = sorted(content_hashes)
    combined = "|".join(sorted_hashes)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def clean_extracted_text(text: str) -> str:
    """
    Clean extracted text by removing repeated headers and trimming whitespace.
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove repeated headers (lines that appear multiple times at start of paragraphs)
    lines = text.split('\n')
    seen_headers = set()
    cleaned_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            cleaned_lines.append('')
            continue
        
        # Check if this looks like a header (short, all caps, or title case)
        is_likely_header = (
            len(line_stripped) < 100 and
            (line_stripped.isupper() or line_stripped.istitle()) and
            line_stripped not in seen_headers
        )
        
        if is_likely_header:
            seen_headers.add(line_stripped)
            cleaned_lines.append(line)
        elif line_stripped.lower() not in [h.lower() for h in seen_headers]:
            cleaned_lines.append(line)
    
    cleaned = '\n'.join(cleaned_lines)
    
    # Final cleanup: remove excessive newlines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    return cleaned.strip()


def extract_rules_from_text(text: str) -> Dict[str, Any]:
    """
    Extract structured rules from combined guideline text using LLM.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")
    
    client = OpenAI(api_key=api_key)
    
    prompt = f"""Sie sind ein Experte für Förderrichtlinien-Analyse. Analysieren Sie den folgenden Text aus Förderrichtlinien-Dokumenten und extrahieren Sie strukturierte Regeln.

RICHTLINIEN-TEXT:
{text[:50000]}  # Limit to 50k chars to avoid token limits

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
- Seien Sie präzise und konkret
- Extrahieren Sie alle relevanten Regeln, auch wenn sie implizit sind

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
                        "content": "Sie sind ein Experte für die Analyse von Förderrichtlinien. Sie extrahieren strukturierte Regeln aus Dokumenten."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=4000,
                timeout=120.0
            )
            openai_ctx["response"] = response

        result_text = response.choices[0].message.content.strip()
        
        # Try to extract JSON from response (might have markdown code blocks)
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            result_text = json_match.group(0)
        
        import json
        rules = json.loads(result_text)
        
        # Ensure all required fields exist
        required_fields = [
            "eligibility_rules", "funding_limits", "required_sections",
            "forbidden_content", "formal_requirements", "evaluation_criteria",
            "deadlines", "important_notes"
        ]
        
        for field in required_fields:
            if field not in rules:
                rules[field] = []
            elif not isinstance(rules[field], list):
                rules[field] = [str(rules[field])]
        
        logger.info(f"Extracted rules with {sum(len(v) for v in rules.values() if isinstance(v, list))} total rules")
        return rules
        
    except Exception as e:
        logger.error(f"Error extracting rules from text: {str(e)}")
        raise


def process_guidelines_for_funding_program(
    funding_program_id: int,
    db: Session
) -> Optional[FundingProgramGuidelinesSummary]:
    """
    Process all guideline documents for a funding program:
    1. Get all guideline documents
    2. Extract text from each
    3. Combine and clean text
    4. Compute combined hash
    5. Check if hash changed
    6. If changed, extract rules and store
    """
    # Get all guideline documents for this funding program
    guideline_docs = db.query(FundingProgramDocument).filter(
        FundingProgramDocument.funding_program_id == funding_program_id,
        FundingProgramDocument.category == "guidelines"
    ).all()
    
    if not guideline_docs:
        logger.info(f"No guideline documents found for funding_program_id={funding_program_id}")
        return None
    
    # Get file records and extract text
    file_hashes = []
    extracted_texts = []
    
    for doc in guideline_docs:
        file_record = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
        if not file_record:
            logger.warning(f"File record not found for document {doc.id}")
            continue
        
        file_hashes.append(file_record.content_hash)
        
        # Get extracted text from cache
        text = get_cached_document_text(db, file_record.content_hash)
        if text:
            extracted_texts.append(text)
        else:
            logger.warning(f"No extracted text found for file {file_record.id} (hash: {file_record.content_hash})")
    
    if not extracted_texts:
        logger.warning(f"No extracted text available for funding_program_id={funding_program_id}")
        return None
    
    # Combine all texts
    combined_text = "\n\n".join(extracted_texts)
    
    # Clean text
    cleaned_text = clean_extracted_text(combined_text)
    
    # Compute combined hash
    combined_hash = compute_combined_hash(file_hashes)
    
    # Check if summary exists and hash matches
    existing_summary = db.query(FundingProgramGuidelinesSummary).filter(
        FundingProgramGuidelinesSummary.funding_program_id == funding_program_id
    ).first()
    
    if existing_summary and existing_summary.source_file_hash == combined_hash:
        logger.info(f"Guidelines summary unchanged for funding_program_id={funding_program_id} (hash: {combined_hash[:16]}...)")
        return existing_summary
    
    # Hash changed or no summary exists - regenerate
    logger.info(f"Regenerating guidelines summary for funding_program_id={funding_program_id} (hash: {combined_hash[:16]}...)")
    
    # Extract rules using LLM
    rules_json = extract_rules_from_text(cleaned_text)
    
    # Create or update summary
    if existing_summary:
        existing_summary.rules_json = rules_json
        existing_summary.source_file_hash = combined_hash
        db.commit()
        db.refresh(existing_summary)
        logger.info(f"Updated guidelines summary for funding_program_id={funding_program_id}")
        return existing_summary
    else:
        new_summary = FundingProgramGuidelinesSummary(
            funding_program_id=funding_program_id,
            rules_json=rules_json,
            source_file_hash=combined_hash
        )
        db.add(new_summary)
        db.commit()
        db.refresh(new_summary)
        logger.info(f"Created new guidelines summary for funding_program_id={funding_program_id}")
        return new_summary
