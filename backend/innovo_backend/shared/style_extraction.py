"""
Style extraction utilities for Alte Vorhabensbeschreibung module.
Extracts writing style patterns, tone, structure, and storytelling flow from historical documents.
Focuses ONLY on writing behavior, NOT domain facts.
"""
import logging
import hashlib
import os
import json
from typing import List, Dict, Any
from openai import OpenAI
from innovo_backend.shared.observability import log_openai_call

logger = logging.getLogger(__name__)


def compute_combined_hash(content_hashes: List[str]) -> str:
    sorted_hashes = sorted(content_hashes)
    combined_string = "|".join(sorted_hashes)
    return hashlib.sha256(combined_string.encode("utf-8")).hexdigest()


def generate_style_profile(doc_texts: List[str]) -> Dict[str, Any]:
    if not doc_texts:
        raise ValueError("No document texts provided for style extraction")

    combined_text = "\n\n---DOCUMENT_SEPARATOR---\n\n".join(doc_texts)

    if len(combined_text) > 100000:
        logger.warning(
            "Combined text too long (%s chars), truncating to 100k chars", len(combined_text)
        )
        combined_text = combined_text[:100000]

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")

    client = OpenAI(api_key=api_key)

    prompt = f"""You are an expert in analyzing writing styles and document structure. Your task is to extract ONLY writing style patterns, tone, structure, and storytelling techniques from the provided historical Vorhabensbeschreibung documents.

CRITICAL: Do NOT extract factual content, domain knowledge, or specific information. Focus ONLY on HOW the text is written, not WHAT it says.

Here are the combined texts from historical Vorhabensbeschreibung documents:
---
{combined_text}
---

Extract the following categories of writing style information and present them as a JSON object. Each category should be a list of strings describing patterns, characteristics, or rules.

Categories to extract:
1. structure_patterns: How the document is organized
2. tone_characteristics: The tone and voice used
3. writing_style_rules: Specific writing conventions observed
4. storytelling_flow: How information is presented narratively
5. common_section_headings: Typical section headings or structural elements

IMPORTANT:
- Ignore tables, images, and visual elements (focus only on text)
- Do NOT extract domain-specific facts or content
- Focus on writing patterns, not information content
- If a category has no clear patterns, provide an empty list

Output ONLY the JSON object. Do not include any other text or explanations.
"""

    approx_tokens = len(prompt) // 4
    logger.info("LLM style extraction prompt size (chars): %s", len(prompt))
    logger.info("LLM style extraction tokens: %s", approx_tokens)
    try:
        with log_openai_call(logger, "generate_style_profile", __file__, "gpt-4o-mini") as openai_ctx:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert in analyzing writing styles and document structure. You extract writing patterns into JSON, ignoring factual content.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=2000,
                timeout=180.0,
            )
            openai_ctx["response"] = response

        style_json_str = response.choices[0].message.content
        style_profile = json.loads(style_json_str)

        required_keys = [
            "structure_patterns",
            "tone_characteristics",
            "writing_style_rules",
            "storytelling_flow",
            "common_section_headings",
        ]
        for key in required_keys:
            if key not in style_profile:
                style_profile[key] = []
            elif not isinstance(style_profile[key], list):
                style_profile[key] = []

        logger.info(
            "Successfully extracted style profile with %s total patterns",
            sum(len(v) for v in style_profile.values()),
        )
        return style_profile

    except Exception as e:
        logger.error("Error extracting style profile: %s", str(e))
        raise
