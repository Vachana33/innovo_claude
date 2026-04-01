"""
Documents router — CRUD + generation endpoints.
"""
import json
import logging
import os
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from innovo_backend.shared.database import get_db
from innovo_backend.shared.dependencies import get_current_user
from innovo_backend.shared.models import Company, Document, FundingProgram, ProjectContext, User
from innovo_backend.shared.observability import log_openai_call, get_request_id
from innovo_backend.shared.posthog_client import capture_event
from innovo_backend.shared.schemas import DocumentResponse, DocumentUpdate, DocumentListItem
from innovo_backend.shared.template_resolver import get_template_for_document, resolve_template

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_owned_document(document_id: int, user_email: str, db: Session) -> Document:
    """Load a document and verify the caller owns it via company FK."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    company = db.query(Company).filter(
        Company.id == document.company_id,
        Company.user_email == user_email,
    ).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if hasattr(document, "chat_history") and document.chat_history is None:
        document.chat_history = []

    return document


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/documents", response_model=List[DocumentListItem])
def list_documents(
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    try:
        documents = (
            db.query(Document)
            .join(Company)
            .filter(Company.user_email == current_user.email)
            .order_by(Document.updated_at.desc())
            .all()
        )

        result = []
        for doc in documents:
            company = db.query(Company).filter(Company.id == doc.company_id).first()
            company_name = company.name if company else f"Company {doc.company_id}"

            funding_program_title = None
            if doc.funding_program_id:
                fp = db.query(FundingProgram).filter(FundingProgram.id == doc.funding_program_id).first()
                funding_program_title = fp.title if fp else None

            result.append(DocumentListItem(
                id=doc.id,
                company_id=doc.company_id,
                company_name=company_name,
                funding_program_id=doc.funding_program_id,
                funding_program_title=funding_program_title,
                type=doc.type,
                title=getattr(doc, "title", None),
                updated_at=doc.updated_at,
            ))

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch documents: {str(e)}",
        ) from e


@router.get("/documents/by-id/{document_id}", response_model=DocumentResponse)
def get_document_by_id(
    document_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    return _get_owned_document(document_id, current_user.email, db)


@router.get("/documents/{company_id}/vorhabensbeschreibung", response_model=DocumentResponse)
def get_document(
    company_id: int,
    funding_program_id: Optional[int] = Query(None),
    template_id: Optional[str] = Query(None),
    template_name: Optional[str] = Query(None),
    title: Optional[str] = Query(None),
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """
    Create a new document for a company or return the existing one (legacy mode).
    When funding_program_id is provided, always creates a new document.
    """
    template_id = (template_id.strip() if isinstance(template_id, str) else None) or None
    template_name = (template_name.strip() if isinstance(template_name, str) else None) or None
    doc_title = (title.strip() if isinstance(title, str) and title else None) or None

    company = db.query(Company).filter(
        Company.id == company_id,
        Company.user_email == current_user.email,
    ).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    document = None

    if funding_program_id:
        funding_program = db.query(FundingProgram).filter(
            FundingProgram.id == funding_program_id,
            FundingProgram.user_email == current_user.email,
        ).first()
        if not funding_program:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funding program not found")

        doc_template_id = None
        doc_template_name = None

        if template_id:
            try:
                doc_template_id = _uuid.UUID(template_id)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid template_id format: {template_id}",
                ) from None
        elif template_name:
            doc_template_name = template_name
        elif funding_program.template_name:
            doc_template_name = funding_program.template_name

        try:
            if doc_template_id:
                template = resolve_template("user", str(doc_template_id), db, current_user.email)
            elif doc_template_name:
                template = resolve_template("system", doc_template_name, db, current_user.email)
            else:
                template = resolve_template("system", "wtt_v1", db, current_user.email)
        except Exception:
            logger.warning("Failed to resolve template, using empty sections")
            template = {"sections": []}

        sections = [{**s, "content": s.get("content", "")} for s in template.get("sections", [])]

        document = Document(
            company_id=company_id,
            funding_program_id=funding_program_id,
            type="vorhabensbeschreibung",
            content_json={"sections": sections},
            template_id=doc_template_id,
            template_name=doc_template_name,
            title=doc_title,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
    else:
        # Legacy: return or create single doc per company
        document = (
            db.query(Document)
            .filter(
                Document.company_id == company_id,
                Document.type == "vorhabensbeschreibung",
                Document.funding_program_id.is_(None),
            )
            .first()
        )

        if not document:
            try:
                template = resolve_template("system", "wtt_v1", db, current_user.email)
            except Exception:
                template = {"sections": []}

            sections = [{**s, "content": s.get("content", "")} for s in template.get("sections", [])]
            document = Document(
                company_id=company_id,
                type="vorhabensbeschreibung",
                content_json={"sections": sections},
            )
            db.add(document)
            db.commit()
            db.refresh(document)

    if hasattr(document, "chat_history") and document.chat_history is None:
        document.chat_history = []

    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    document = _get_owned_document(document_id, current_user.email, db)
    try:
        db.delete(document)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document",
        ) from e


@router.put("/documents/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: int,
    document_data: DocumentUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    document = _get_owned_document(document_id, current_user.email, db)

    document.content_json = document_data.content_json
    flag_modified(document, "content_json")
    document.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(document)
        return document
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document",
        ) from e


@router.post("/documents/{document_id}/generate-content", response_model=DocumentResponse)
def generate_content(
    document_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """
    ROLE: INITIAL CONTENT GENERATION

    Generate content for document sections using OpenAI.
    Requires company preprocessing to be completed.
    """
    from openai import OpenAI  # noqa: PLC0415
    from innovo_backend.services.documents.service import _generate_batch_content  # noqa: PLC0415

    document = _get_owned_document(document_id, current_user.email, db)
    company = db.query(Company).filter(Company.id == document.company_id).first()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key not configured",
        )

    # Load project context if this document belongs to a project
    ctx = None
    if document.project_id:
        ctx = db.query(ProjectContext).filter(
            ProjectContext.project_id == document.project_id
        ).first()

    sections = (document.content_json or {}).get("sections", [])
    if not sections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no sections to generate",
        )

    # Load funding program rules if not in ctx
    funding_program_rules = None
    if not ctx and document.funding_program_id:
        from innovo_backend.shared.models import FundingProgramGuidelinesSummary  # noqa: PLC0415
        summary = db.query(FundingProgramGuidelinesSummary).filter(
            FundingProgramGuidelinesSummary.funding_program_id == document.funding_program_id
        ).first()
        if summary:
            funding_program_rules = summary.rules_json

    client = OpenAI(api_key=api_key)

    BATCH_SIZE = 4
    for i in range(0, len(sections), BATCH_SIZE):
        batch = sections[i: i + BATCH_SIZE]
        try:
            if ctx:
                generated = _generate_batch_content(sections=batch, document=document, ctx=ctx, client=client, db=db)
            else:
                generated = _generate_batch_content(
                    sections=batch,
                    document=document,
                    client=client,
                    db=db,
                    company_name=company.name if company else "Unknown Company",
                    company_profile=company.company_profile if company else None,
                    website_clean_text=company.website_clean_text if company else None,
                    transcript_clean=company.transcript_clean if company else None,
                    funding_program_rules=funding_program_rules,
                )

            for section in sections:
                if section.get("id") in generated:
                    section["content"] = generated[section["id"]]

        except Exception as e:
            logger.error("Batch %d generation failed: %s", i, str(e))

    document.content_json = {"sections": sections}
    flag_modified(document, "content_json")
    document.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(document)

    return document
