"""
Structured extraction utilities for company data.
Phase 2B: Pure structured extraction (NO content generation).
"""
import os
import json
import logging
from typing import Dict, Any
from openai import OpenAI
from innovo_backend.shared.observability import log_openai_call

logger = logging.getLogger(__name__)

MAX_INPUT_TEXT_LENGTH = 50000


def extract_company_profile(website_text: str, transcript_text: str) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment")
        raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")

    try:
        client = OpenAI(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {str(e)}")
        raise

    def smart_truncate(text: str, max_length: int) -> str:
        if not text or len(text) <= max_length:
            return text or ""
        first_part = text[:int(max_length * 0.6)]
        last_part = text[-int(max_length * 0.4):]
        return f"{first_part}\n\n[... content truncated ...]\n\n{last_part}"

    website_processed = smart_truncate(website_text, MAX_INPUT_TEXT_LENGTH)
    transcript_processed = smart_truncate(transcript_text, MAX_INPUT_TEXT_LENGTH)

    prompt = f"""You are a data extraction system. Your task is to extract ONLY factual information from the provided text.

CRITICAL RULES:
- Extract ONLY facts that are explicitly stated in the text
- Do NOT generate, create, or invent any information
- Do NOT write prose, descriptions, or funding-style text
- Do NOT paraphrase or summarize - extract exact facts only
- If information is missing, use null (not "unknown" unless explicitly stated)
- Use German for extracted values if the source text is in German
- Use English for keys only

INPUT TEXT:
Website Content:
{website_processed}

Meeting Transcript:
{transcript_processed}

EXTRACTION TASK:
Extract the following structured information. If a field cannot be determined from the text, use null.

REQUIRED OUTPUT FORMAT (JSON):
{{
  "industry": "string or null - Company's industry/sector",
  "products_or_services": ["string"] or null - List of products/services mentioned",
  "business_model": "string or null - How the company makes money",
  "market": "string or null - Target market/customers",
  "innovation_focus": "string or null - Innovation focus areas",
  "company_size": "string or null - Company size if mentioned",
  "location": "string or null - Company location if mentioned",
  "known_gaps": ["string"] - List of important information that is missing
}}

IMPORTANT:
- Return ONLY valid JSON
- Do NOT include any text outside the JSON object
- Use null for missing information"""

    try:
        logger.info("Starting company profile extraction")

        with log_openai_call(logger, "extract_company_profile", __file__, "gpt-4o-mini") as openai_ctx:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data extraction system. Extract ONLY factual information from text. Return structured JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout=60.0,
            )
            openai_ctx["response"] = response

        response_text = response.choices[0].message.content
        profile = json.loads(response_text)

        required_fields = [
            "industry", "products_or_services", "business_model", "market",
            "innovation_focus", "company_size", "location", "known_gaps",
        ]
        for field in required_fields:
            if field not in profile:
                profile[field] = None if field != "known_gaps" else []

        if not isinstance(profile.get("known_gaps"), list):
            profile["known_gaps"] = []

        logger.info("Company profile extraction completed successfully")
        return profile

    except Exception as e:
        logger.error(f"Company profile extraction failed: {str(e)}")
        raise
