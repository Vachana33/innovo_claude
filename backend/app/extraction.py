"""
Structured extraction utilities for company data.

Phase 2B: Pure structured extraction (NO content generation).

This module extracts structured facts from raw company text data.
It does NOT generate prose, funding-style text, or creative content.
It ONLY extracts factual information into structured JSON format.
"""
import os
import json
import logging
from typing import Dict, Any
from openai import OpenAI
from app.observability import log_openai_call

logger = logging.getLogger(__name__)

# Maximum text length to send to LLM (to avoid token limits)
MAX_INPUT_TEXT_LENGTH = 50000


def extract_company_profile(website_text: str, transcript_text: str) -> Dict[str, Any]:
    """
    Extract structured company profile from raw website and transcript text.

    This function performs PURE EXTRACTION - it only extracts factual information
    that exists in the input text. It does NOT generate prose, creative content,
    or funding-style text.

    Args:
        website_text: Raw text extracted from company website
        transcript_text: Raw text transcribed from audio recording

    Returns:
        Dictionary with structured company profile containing:
        - industry: Company's industry/sector (string or null)
        - products_or_services: List of products/services (list or null)
        - business_model: Business model description (string or null)
        - market: Target market/customers (string or null)
        - innovation_focus: Innovation focus areas (string or null)
        - company_size: Company size if inferable (string or null)
        - location: Company location if inferable (string or null)
        - known_gaps: List of missing important information (list)

    Raises:
        ValueError: If OpenAI API key is not configured
        Exception: If extraction fails (logged but not suppressed)

    Example:
        >>> website = "TechCorp develops AI solutions for healthcare..."
        >>> transcript = "We have 50 employees in Berlin..."
        >>> profile = extract_company_profile(website, transcript)
        >>> print(profile['industry'])
        'Healthcare Technology'
    """
    # Get OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment")
        raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")

    # Initialize OpenAI client
    try:
        client = OpenAI(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {str(e)}")
        raise

    # Truncate input text if too long (keep beginning and end)
    def smart_truncate(text: str, max_length: int) -> str:
        """Truncate text intelligently, keeping beginning and end if too long."""
        if not text or len(text) <= max_length:
            return text or ""
        first_part = text[:int(max_length * 0.6)]
        last_part = text[-int(max_length * 0.4):]
        return f"{first_part}\n\n[... content truncated ...]\n\n{last_part}"

    website_processed = smart_truncate(website_text, MAX_INPUT_TEXT_LENGTH)
    transcript_processed = smart_truncate(transcript_text, MAX_INPUT_TEXT_LENGTH)

    # Build extraction prompt - CRITICAL: Emphasize extraction only, no generation
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
  "company_size": "string or null - Company size if mentioned (e.g., '50 employees', 'startup', 'SME')",
  "location": "string or null - Company location if mentioned",
  "known_gaps": ["string"] - List of important information that is missing (e.g., 'revenue', 'founding_year', 'funding_status')
}}

EXTRACTION GUIDELINES:
- industry: Extract the specific industry/sector (e.g., "Healthcare Technology", "Manufacturing", "Software Development")
- products_or_services: Extract specific products/services mentioned (e.g., ["AI diagnostic tools", "Cloud platform"])
- business_model: Extract how company makes money (e.g., "B2B SaaS", "Product sales", "Consulting services")
- market: Extract target market (e.g., "Healthcare providers", "SMEs in Germany", "Enterprise customers")
- innovation_focus: Extract innovation areas (e.g., "AI/ML", "IoT", "Digital transformation")
- company_size: Extract if mentioned (e.g., "50 employees", "startup", "SME", "50-100 employees")
- location: Extract if mentioned (e.g., "Berlin, Germany", "Munich")
- known_gaps: List what important information is missing (e.g., ["revenue", "founding_year", "funding_status", "key_competitors"])

IMPORTANT:
- Return ONLY valid JSON
- Do NOT include any text outside the JSON object
- Do NOT add explanations or comments
- Use null for missing information (not "unknown" or "not mentioned")
- Extract facts only - no creative writing or generation"""

    approx_tokens = len(prompt) // 4
    logger.info("LLM company profile extraction prompt size (chars): %s", len(prompt))
    logger.info("LLM company profile extraction tokens: %s", approx_tokens)
    try:
        logger.info("Starting company profile extraction")

        with log_openai_call(logger, "extract_company_profile", __file__, "gpt-4o-mini") as openai_ctx:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data extraction system. Extract ONLY factual information from text. Do NOT generate, create, or invent any information. Return structured JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,  # Use 0.0 for deterministic extraction
                response_format={"type": "json_object"},  # Force JSON output
                timeout=60.0  # 1 minute timeout
            )
            openai_ctx["response"] = response

        response_text = response.choices[0].message.content
        logger.info("OpenAI response received for company profile extraction")

        # Parse JSON response
        try:
            profile = json.loads(response_text)

            # Validate required fields exist
            required_fields = [
                "industry", "products_or_services", "business_model", "market",
                "innovation_focus", "company_size", "location", "known_gaps"
            ]

            # Ensure all required fields exist (add null if missing)
            for field in required_fields:
                if field not in profile:
                    profile[field] = None if field != "known_gaps" else []
                    logger.warning(f"Missing field '{field}' in extraction response, set to default")

            # Ensure known_gaps is a list
            if not isinstance(profile.get("known_gaps"), list):
                profile["known_gaps"] = []

            logger.info("Company profile extraction completed successfully")
            return profile

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.error(f"Response text: {response_text[:500]}")
            raise ValueError(f"Invalid JSON response from extraction: {str(e)}")

    except Exception as e:
        logger.error(f"Company profile extraction failed: {str(e)}")
        raise
