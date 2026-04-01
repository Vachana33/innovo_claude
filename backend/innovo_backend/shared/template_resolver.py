"""Phase 2.5: Template Resolver"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from innovo_backend.services.templates.registry import get_template as get_system_template
from innovo_backend.shared.models import UserTemplate

logger = logging.getLogger(__name__)


def resolve_template(
    template_source: Optional[str],
    template_ref: Optional[str],
    db: Optional[Session] = None,
    user_email: Optional[str] = None,
) -> Dict[str, Any]:
    if template_source is None and template_ref:
        logger.warning(f"Legacy template resolution: treating template_ref '{template_ref}' as system template")
        template_source = "system"

    if template_source not in ["system", "user"]:
        raise ValueError(f"Invalid template_source: '{template_source}'. Must be 'system' or 'user'")

    if not template_ref:
        raise ValueError("template_ref is required when template_source is set")

    if template_source == "system":
        logger.info(f"[TEMPLATE RESOLVER] Resolving system template: {template_ref}")
        try:
            template = get_system_template(template_ref)
            logger.info(f"[TEMPLATE RESOLVER] Successfully resolved system template: {template_ref}")
            return template
        except (KeyError, ValueError) as e:
            logger.error(f"[TEMPLATE RESOLVER] Failed to resolve system template '{template_ref}': {str(e)}")
            raise

    elif template_source == "user":
        if not db:
            raise ValueError("Database session required for user template resolution")
        if not user_email:
            raise ValueError("user_email required for user template resolution")

        logger.info(f"[TEMPLATE RESOLVER] Resolving user template: {template_ref} for user {user_email}")
        try:
            import uuid
            template_id = uuid.UUID(template_ref)
            user_template = db.query(UserTemplate).filter(
                UserTemplate.id == template_id,
                UserTemplate.user_email == user_email,
            ).first()

            if not user_template:
                raise ValueError(f"User template '{template_ref}' not found or access denied")

            template_structure = user_template.template_structure
            if not isinstance(template_structure, dict):
                raise ValueError(f"User template '{template_ref}' has invalid structure")
            if "sections" not in template_structure:
                raise ValueError(f"User template '{template_ref}' missing 'sections' key")
            if not isinstance(template_structure["sections"], list):
                raise ValueError(f"User template '{template_ref}' sections must be a list")

            logger.info(f"[TEMPLATE RESOLVER] Successfully resolved user template: {template_ref}")
            return template_structure

        except ValueError as e:
            if "not found" in str(e) or "invalid" in str(e).lower():
                raise
            raise ValueError(f"Invalid user template reference: {template_ref}") from e
        except Exception as e:
            raise ValueError(f"Failed to resolve user template: {str(e)}") from e

    raise ValueError(f"Unsupported template_source: {template_source}")


def get_template_for_document(document, db: Session, user_email: Optional[str] = None) -> Dict[str, Any]:
    if document.template_id:
        if not user_email and hasattr(document, "company") and document.company:
            user_email = document.company.user_email
        return resolve_template(
            template_source="user",
            template_ref=str(document.template_id),
            db=db,
            user_email=user_email,
        )

    if document.template_name:
        return resolve_template(
            template_source="system",
            template_ref=document.template_name,
            db=db,
            user_email=user_email,
        )

    try:
        return resolve_template(template_source="system", template_ref="wtt_v1", db=db, user_email=user_email)
    except (KeyError, ValueError) as e:
        raise ValueError(f"Default template 'wtt_v1' not available.") from e
