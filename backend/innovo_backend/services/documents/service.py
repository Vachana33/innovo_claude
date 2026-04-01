"""
Documents service — shared generation logic callable from both the documents router
and the projects router background task.
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _generate_batch_content(
    sections: List[dict],
    document,
    project=None,
    ctx=None,
    client=None,
    db=None,
    # v1 fallback kwargs (used when project/ctx are not available)
    company_name: str = "Unknown Company",
    company_profile: Optional[Dict[str, Any]] = None,
    website_clean_text: Optional[str] = None,
    transcript_clean: Optional[str] = None,
    company_id: Optional[int] = None,
    funding_program_rules: Optional[Dict[str, Any]] = None,
    style_profile: Optional[Dict[str, Any]] = None,
    max_retries: int = 2,
) -> Dict[str, str]:
    """
    ROLE: INITIAL GENERATION

    Creates section content from scratch for empty or new sections.
    Used ONLY during first draft generation — never for chat-based editing.

    Returns a dictionary mapping section_id to generated content.
    Implements retry logic with strict JSON validation.
    """
    from innovo_backend.services.documents.prompt_builder import PromptBuilder  # noqa: PLC0415
    from innovo_backend.shared.observability import log_openai_call  # noqa: PLC0415

    if ctx is not None:
        builder = PromptBuilder(context=ctx)
    elif project is not None and db is not None:
        # Load context from project
        from innovo_backend.shared.models import ProjectContext  # noqa: PLC0415
        ctx_row = db.query(ProjectContext).filter(ProjectContext.project_id == project.id).first()
        builder = PromptBuilder(context=ctx_row)
    else:
        builder = PromptBuilder(
            company_name=company_name,
            company_profile=company_profile,
            website_clean_text=website_clean_text,
            transcript_clean=transcript_clean,
            company_id=company_id,
            funding_rules=funding_program_rules,
            style_profile=style_profile,
        )

    section_ids = [s.get("id", "") for s in sections if s.get("type") != "milestone_table"]
    prompt = builder.build_generation_prompt(sections)

    approx_tokens = len(prompt) // 4
    logger.info("LLM batch generation prompt size (chars): %s", len(prompt))
    logger.info("LLM batch generation prompt tokens: %s", approx_tokens)

    for attempt in range(max_retries + 1):
        try:
            with log_openai_call(logger, "_generate_batch_content", __file__, "gpt-4o-mini") as openai_ctx:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "Sie sind ein professioneller Berater, der sich auf Förderanträge spezialisiert hat. Sie schreiben klare, strukturierte und überzeugende Projektbeschreibungen auf Deutsch im formellen Fördermittel-Stil.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    response_format={"type": "json_object"},
                    timeout=120.0,
                )
                openai_ctx["response"] = response

            response_text = response.choices[0].message.content
            logger.info("OpenAI response received for batch (attempt %d)", attempt + 1)

            try:
                generated_content = json.loads(response_text)

                missing_ids = [sid for sid in section_ids if sid not in generated_content]
                if missing_ids:
                    logger.warning("Missing section IDs in LLM response: %s. Inserting empty placeholders.", missing_ids)
                    for sid in missing_ids:
                        generated_content[sid] = ""

                for sid, content in generated_content.items():
                    if not isinstance(content, str):
                        raise ValueError(f"Content for section {sid} is not a string: {type(content)}")

                logger.info("Successfully validated JSON for batch with %d sections", len(generated_content))
                return generated_content

            except json.JSONDecodeError as e:
                logger.warning("JSON parse error (attempt %d): %s", attempt + 1, str(e))
                if attempt < max_retries:
                    continue
                raise ValueError(f"Failed to parse JSON after {max_retries + 1} attempts: {str(e)}") from e

            except ValueError as e:
                logger.warning("JSON validation error (attempt %d): %s", attempt + 1, str(e))
                if attempt < max_retries:
                    continue
                raise

        except Exception as e:
            if attempt < max_retries:
                logger.warning("OpenAI API error (attempt %d): %s. Retrying...", attempt + 1, str(e))
                continue
            logger.error("OpenAI API error after %d attempts: %s", max_retries + 1, str(e))
            raise

    raise ValueError("Failed to generate content after all retries")
