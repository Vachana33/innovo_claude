"""
project_chat_service — handles the project-scoped chatbot conversation.

Loads ProjectContext as the LLM system prompt, detects company corrections in the
assistant response, merges them into company_profile_json (same logic as
PATCH /projects/{id}/context), and persists both chat turns.
"""
import json
import logging
import os
import uuid

from sqlalchemy.orm import Session

from app.models import Project, ProjectContext, ProjectChatMessage

logger = logging.getLogger(__name__)

# Weight applied to company data in completeness scoring.
# Mirrors CONTEXT_SCORE_WEIGHTS["company"] in context_assembler.py.
_COMPANY_SCORE_WEIGHT = 25


def _build_system_prompt(ctx: ProjectContext | None) -> str:
    """
    Construct the LLM system prompt from available ProjectContext fields.
    All fields are optional; present ones are injected as labelled sections.
    """
    parts = [
        "Du bist ein Assistent, der beim Verfassen von Förderanträgen (Vorhabensbeschreibungen) hilft.",
        "Du kennst den Projektkontext und kannst Fragen dazu beantworten sowie fehlende Informationen aufnehmen.",
        "",
    ]

    if ctx is None:
        parts.append("Es ist noch kein Projektkontext verfügbar.")
        return "\n".join(parts)

    if ctx.company_profile_json:
        try:
            profile = json.loads(ctx.company_profile_json)
            parts.append("=== FIRMENPROFIL ===")
            parts.append(json.dumps(profile, ensure_ascii=False, indent=2))
            parts.append("")
        except (json.JSONDecodeError, TypeError):
            pass

    if ctx.funding_rules_json:
        try:
            rules = json.loads(ctx.funding_rules_json)
            parts.append("=== FÖRDERRICHTLINIEN ===")
            parts.append(json.dumps(rules, ensure_ascii=False, indent=2))
            parts.append("")
        except (json.JSONDecodeError, TypeError):
            pass

    if ctx.domain_research_json:
        try:
            research = json.loads(ctx.domain_research_json)
            parts.append("=== DOMÄNENRECHERCHE ===")
            parts.append(json.dumps(research, ensure_ascii=False, indent=2))
            parts.append("")
        except (json.JSONDecodeError, TypeError):
            pass

    if ctx.retrieved_examples_json:
        try:
            examples = json.loads(ctx.retrieved_examples_json)
            parts.append("=== REFERENZBEISPIELE ===")
            parts.append(json.dumps(examples, ensure_ascii=False, indent=2))
            parts.append("")
        except (json.JSONDecodeError, TypeError):
            pass

    if ctx.style_profile_json:
        try:
            style = json.loads(ctx.style_profile_json)
            parts.append("=== STILPROFIL ===")
            parts.append(json.dumps(style, ensure_ascii=False, indent=2))
            parts.append("")
        except (json.JSONDecodeError, TypeError):
            pass

    parts.append(
        "Wenn der Nutzer Informationen über das Unternehmen bereitstellt (z.B. Produkte, Beschreibung, Website), "
        "bestätige diese und merke sie dir für spätere Generierungen."
    )

    return "\n".join(parts)


def _extract_company_corrections(assistant_text: str, user_message: str) -> dict:
    """
    Detect if the conversation turn contains company information provided by the user.
    Returns a dict with keys 'description' and/or 'website' when found.
    Conservative: only extracts when the user message reads as factual company info.

    This is a lightweight heuristic; it intentionally errs on the side of not
    extracting rather than misclassifying questions or instructions.
    """
    corrections: dict = {}
    text = user_message.strip()

    # Detect website URLs
    import re
    url_match = re.search(r'https?://\S+', text)
    if url_match:
        corrections["website"] = url_match.group(0).rstrip(".,;)")

    # Detect company description phrases
    description_triggers = [
        "baut ", "entwickelt ", "produziert ", "bietet ", "ist ein",
        "is a ", "builds ", "develops ", "manufactures ", "provides ",
        "main product", "hauptprodukt", "beschreibung:", "description:",
        "das unternehmen ", "the company ",
    ]
    lower = text.lower()
    if any(trigger in lower for trigger in description_triggers):
        corrections["description"] = text

    return corrections


def _merge_company_corrections(ctx: ProjectContext, corrections: dict, db: Session) -> None:
    """
    Merge provided company corrections into ctx.company_profile_json.
    Recalculates completeness_score when previous status was not_found.
    Identical logic to PATCH /projects/{id}/context in projects.py.
    """
    if not corrections:
        return

    profile: dict = {}
    if ctx.company_profile_json:
        try:
            profile = json.loads(ctx.company_profile_json)
        except (json.JSONDecodeError, TypeError):
            profile = {}

    if corrections.get("website"):
        profile["website"] = corrections["website"]
    if corrections.get("description"):
        profile["description"] = corrections["description"]
    profile["source"] = "user_provided"

    ctx.company_profile_json = json.dumps(profile)

    previous_status = ctx.company_discovery_status
    ctx.company_discovery_status = "partial"

    if ctx.completeness_score is None:
        ctx.completeness_score = 0
    if previous_status == "not_found":
        ctx.completeness_score += _COMPANY_SCORE_WEIGHT

    db.commit()
    db.refresh(ctx)


def handle_user_message(project_id: str, user_message: str, db: Session) -> str:
    """
    Handle one user turn in the project chatbot.

    1. Load ProjectContext.
    2. Build system prompt from context fields.
    3. Call the LLM (gpt-4o-mini, same model as the rest of the system).
    4. If the user message contains company corrections, merge them into
       company_profile_json with the same logic as PATCH /projects/{id}/context.
    5. Persist both turns (user + assistant) to project_chat_messages.
    6. Return the assistant response text.
    """
    from openai import OpenAI

    ctx = db.query(ProjectContext).filter(
        ProjectContext.project_id == project_id
    ).first()

    system_prompt = _build_system_prompt(ctx)

    # Load full conversation history for multi-turn context (last 20 turns)
    history = (
        db.query(ProjectChatMessage)
        .filter(ProjectChatMessage.project_id == project_id)
        .order_by(ProjectChatMessage.created_at.asc())
        .limit(20)
        .all()
    )
    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": user_message})

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
            timeout=120.0,
        )
        assistant_text = response.choices[0].message.content.strip()
    except Exception:
        logger.exception("project_chat_service | LLM call failed for project_id=%s", project_id)
        raise

    # Detect and merge company corrections from user message
    if ctx:
        corrections = _extract_company_corrections(assistant_text, user_message)
        if corrections:
            _merge_company_corrections(ctx, corrections, db)

    # Persist both turns
    user_msg = ProjectChatMessage(
        id=str(uuid.uuid4()),
        project_id=project_id,
        role="user",
        content=user_message,
    )
    assistant_msg = ProjectChatMessage(
        id=str(uuid.uuid4()),
        project_id=project_id,
        role="assistant",
        content=assistant_text,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    db.commit()

    return assistant_text
