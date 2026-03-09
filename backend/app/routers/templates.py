"""
Template API endpoints.

Includes:
- UserTemplate CRUD operations
- Template listing for funding programs
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, FundingProgram, UserTemplate, Document
from app.templates import get_template
from app.schemas import UserTemplateCreate, UserTemplateUpdate, UserTemplateResponse
from sqlalchemy.orm.attributes import flag_modified
import logging
import uuid
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class TemplateResponse(BaseModel):
    """Response model for template endpoint"""
    template_name: str
    sections: list[dict]


@router.get("/templates", response_model=TemplateResponse)
def get_template_for_funding_program(
    funding_program_id: int = Query(..., description="Funding program ID"),
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Get template structure for a funding program.

    OPTIONAL ENDPOINT: This is for debugging/preview only.
    Document creation does not require this endpoint.

    Returns the template structure that would be used to create documents
    for the specified funding program.
    """
    # Verify funding program exists and belongs to current user
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email
    ).first()

    if not funding_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funding program not found"
        )

    if not funding_program.template_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Funding program {funding_program_id} has no template_name configured"
        )

    try:
        template = get_template(funding_program.template_name)
        return TemplateResponse(
            template_name=funding_program.template_name,
            sections=template.get("sections", [])
        )
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) from e


@router.get("/templates/system/{template_name}", response_model=TemplateResponse)
def get_system_template(
    template_name: str,
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Get the full structure of a system template by name.
    Used for copying system template content.
    """
    try:
        template = get_template(template_name)
        return TemplateResponse(
            template_name=template_name,
            sections=template.get("sections", [])
        )
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"System template '{template_name}' not found"
        ) from e


# UserTemplate CRUD endpoints
@router.post("/user-templates", response_model=UserTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_user_template(
    template_data: UserTemplateCreate,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """Create a new user-defined template."""
    if not template_data.name or not template_data.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template name is required"
        )

    # Validate template structure
    if not template_data.sections or not isinstance(template_data.sections, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template must have a sections array"
        )

    # Create template structure
    template_structure = {
        "sections": template_data.sections
    }

    new_template = UserTemplate(
        name=template_data.name.strip(),
        description=template_data.description.strip() if template_data.description else None,
        template_structure=template_structure,
        user_email=current_user.email
    )

    try:
        db.add(new_template)
        db.commit()
        db.refresh(new_template)
        logger.info(f"Created user template '{new_template.name}' (ID: {new_template.id}) for user {current_user.email}")
        # Convert UUID to string for response
        return UserTemplateResponse(
            id=str(new_template.id),
            name=new_template.name,
            description=new_template.description,
            template_structure=new_template.template_structure,
            created_at=new_template.created_at,
            updated_at=new_template.updated_at
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create user template: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create template"
        ) from e


@router.get("/user-templates", response_model=List[UserTemplateResponse])
def list_user_templates(
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """List all user-defined templates for the current user."""
    templates = db.query(UserTemplate).filter(
        UserTemplate.user_email == current_user.email
    ).order_by(UserTemplate.created_at.desc()).all()

    # Convert UUIDs to strings
    return [
        UserTemplateResponse(
            id=str(t.id),
            name=t.name,
            description=t.description,
            template_structure=t.template_structure,
            created_at=t.created_at,
            updated_at=t.updated_at
        )
        for t in templates
    ]


@router.get("/user-templates/{template_id}", response_model=UserTemplateResponse)
def get_user_template(
    template_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """Get a specific user-defined template."""
    try:
        template_uuid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template ID format"
        ) from None

    template = db.query(UserTemplate).filter(
        UserTemplate.id == template_uuid,
        UserTemplate.user_email == current_user.email
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    # Convert UUID to string for response
    return UserTemplateResponse(
        id=str(template.id),
        name=template.name,
        description=template.description,
        template_structure=template.template_structure,
        created_at=template.created_at,
        updated_at=template.updated_at
    )


@router.put("/user-templates/{template_id}", response_model=UserTemplateResponse)
def update_user_template(
    template_id: str,
    template_data: UserTemplateUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """Update a user-defined template."""
    try:
        template_uuid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template ID format"
        ) from None

    template = db.query(UserTemplate).filter(
        UserTemplate.id == template_uuid,
        UserTemplate.user_email == current_user.email
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    # Update fields
    if template_data.name is not None:
        if not template_data.name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template name cannot be empty"
            )
        template.name = template_data.name.strip()

    if template_data.description is not None:
        template.description = template_data.description.strip() if template_data.description else None

    if template_data.sections is not None:
        if not isinstance(template_data.sections, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template sections must be an array"
            )
        template.template_structure = {"sections": template_data.sections}
        flag_modified(template, "template_structure")

    try:
        db.commit()
        db.refresh(template)
        logger.info(f"Updated user template '{template.name}' (ID: {template.id}) for user {current_user.email}")
        # Convert UUID to string for response
        return UserTemplateResponse(
            id=str(template.id),
            name=template.name,
            description=template.description,
            template_structure=template.template_structure,
            created_at=template.created_at,
            updated_at=template.updated_at
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update user template: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update template"
        ) from e


@router.post("/user-templates/duplicate/{template_id}", response_model=UserTemplateResponse, status_code=status.HTTP_201_CREATED)
def duplicate_user_template(
    template_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """Duplicate a user-defined template. Creates a new template with same sections and name suffixed by ' (Copy)'."""
    try:
        template_uuid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template ID format"
        ) from None

    template = db.query(UserTemplate).filter(
        UserTemplate.id == template_uuid,
        UserTemplate.user_email == current_user.email
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    new_name = (template.name or "Template").strip() + " (Copy)"
    new_template = UserTemplate(
        name=new_name,
        description=template.description,
        template_structure=dict(template.template_structure) if template.template_structure else {"sections": []},
        user_email=current_user.email
    )

    try:
        db.add(new_template)
        db.commit()
        db.refresh(new_template)
        logger.info(
            f"Duplicated user template '{template.name}' -> '{new_name}' (ID: {new_template.id}) for user {current_user.email}"
        )
        return UserTemplateResponse(
            id=str(new_template.id),
            name=new_template.name,
            description=new_template.description,
            template_structure=new_template.template_structure,
            created_at=new_template.created_at,
            updated_at=new_template.updated_at
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to duplicate user template: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to duplicate template"
        ) from e


@router.delete("/user-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_template(
    template_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """Delete a user-defined template. Blocked if any document references this template."""
    try:
        template_uuid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template ID format"
        ) from None

    template = db.query(UserTemplate).filter(
        UserTemplate.id == template_uuid,
        UserTemplate.user_email == current_user.email
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    # Block deletion if any document references this template (would break document loading)
    ref_count = db.query(Document).filter(Document.template_id == template_uuid).count()
    if ref_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete template: {ref_count} document(s) use this template. Remove or reassign those documents first."
        )

    try:
        db.delete(template)
        db.commit()
        logger.info(f"Deleted user template '{template.name}' (ID: {template.id}) for user {current_user.email}")
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete user template: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete template"
        ) from e


@router.get("/templates/list", response_model=dict)
def list_all_templates(
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    List all available templates (system + user) for funding program selection.
    Returns both system templates and user-defined templates.
    """
    # System templates
    from app.templates import TEMPLATE_REGISTRY
    system_templates = [
        {"id": name, "name": name, "source": "system"}
        for name in TEMPLATE_REGISTRY.keys()
    ]

    # User templates
    user_templates = db.query(UserTemplate).filter(
        UserTemplate.user_email == current_user.email
    ).order_by(UserTemplate.created_at.desc()).all()

    user_template_list = [
        {"id": str(t.id), "name": t.name, "source": "user", "description": t.description}
        for t in user_templates
    ]

    return {
        "system": system_templates,
        "user": user_template_list
    }
