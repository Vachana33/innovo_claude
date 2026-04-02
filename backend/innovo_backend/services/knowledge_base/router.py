"""
Phase 4 — Knowledge Base router (admin-only)
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from innovo_backend.shared.database import get_db, SessionLocal
from innovo_backend.shared.dependencies import get_current_user, require_admin
from innovo_backend.shared.file_storage import get_or_create_file
from innovo_backend.shared.funding_program_documents import get_file_type_from_filename
from innovo_backend.shared.models import KnowledgeBaseDocument, KnowledgeBaseChunk, FundingProgramSource, FundingProgram, User
from innovo_backend.shared.schemas import KnowledgeBaseDocumentResponse, FundingProgramSourceCreate, FundingProgramSourceResponse
from innovo_backend.services.knowledge_base.retriever import index_document

logger = logging.getLogger(__name__)

router = APIRouter()


def _index_document_in_background(document_id) -> None:
    logger.info("knowledge_base | background indexing started document_id=%s", document_id)
    db = SessionLocal()
    try:
        index_document(document_id, db)
        logger.info("knowledge_base | background indexing completed document_id=%s", document_id)
    except Exception:
        logger.exception("knowledge_base | background indexing failed document_id=%s", document_id)
    finally:
        db.close()


def _scrape_source_in_background(source_id) -> None:
    from innovo_backend.services.knowledge_base.scraper import fetch_and_index  # noqa: PLC0415
    logger.info("knowledge_base | background scrape started source_id=%s", source_id)
    db = SessionLocal()
    try:
        fetch_and_index(source_id, db)
        logger.info("knowledge_base | background scrape completed source_id=%s", source_id)
    except Exception:
        logger.exception("knowledge_base | background scrape failed source_id=%s", source_id)
    finally:
        db.close()


@router.post("/knowledge-base/documents", response_model=KnowledgeBaseDocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_knowledge_base_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = "other",
    program_tag: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    filename = file.filename or "unknown"
    file_type = get_file_type_from_filename(filename)

    if file_type not in ("pdf", "docx", "doc"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{file_type}'. Accepted: pdf, docx, doc.",
        )

    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    file_record, _ = get_or_create_file(db, file_bytes, file_type, filename)
    db.flush()

    kb_doc = KnowledgeBaseDocument(
        filename=filename,
        category=category,
        program_tag=program_tag,
        file_id=file_record.id,
        uploaded_by=current_user.email,
    )
    db.add(kb_doc)
    db.commit()
    db.refresh(kb_doc)

    background_tasks.add_task(_index_document_in_background, kb_doc.id)

    logger.info(
        "knowledge_base | upload: document_id=%s filename=%s category=%s program_tag=%s uploaded_by=%s",
        kb_doc.id, filename, category, program_tag, current_user.email,
    )
    return kb_doc


@router.get("/knowledge-base/documents", response_model=List[KnowledgeBaseDocumentResponse])
def list_knowledge_base_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    return db.query(KnowledgeBaseDocument).order_by(KnowledgeBaseDocument.created_at.desc()).all()


@router.delete("/knowledge-base/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    doc = db.query(KnowledgeBaseDocument).filter(KnowledgeBaseDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    db.delete(doc)
    db.commit()

    logger.info("knowledge_base | delete: document_id=%s deleted_by=%s", document_id, current_user.email)


@router.post("/knowledge-base/funding-sources", response_model=FundingProgramSourceResponse, status_code=status.HTTP_201_CREATED)
def add_funding_source(
    payload: FundingProgramSourceCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    program = db.query(FundingProgram).filter(FundingProgram.id == payload.funding_program_id).first()
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FundingProgram {payload.funding_program_id} not found",
        )

    source = FundingProgramSource(
        funding_program_id=payload.funding_program_id,
        url=payload.url,
        label=payload.label,
        status="pending",
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    background_tasks.add_task(_scrape_source_in_background, source.id)

    logger.info(
        "knowledge_base | funding-source added: source_id=%s url=%s program_id=%s by=%s",
        source.id, source.url, source.funding_program_id, current_user.email,
    )
    return source


@router.get("/knowledge-base/funding-sources", response_model=List[FundingProgramSourceResponse])
def list_funding_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    return db.query(FundingProgramSource).order_by(FundingProgramSource.created_at.desc()).all()


@router.delete("/knowledge-base/funding-sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_funding_source(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    source = db.query(FundingProgramSource).filter(FundingProgramSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    db.delete(source)
    db.commit()

    logger.info("knowledge_base | funding-source deleted: source_id=%s by=%s", source_id, current_user.email)


@router.post("/knowledge-base/funding-sources/{source_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_funding_source(
    source_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    source = db.query(FundingProgramSource).filter(FundingProgramSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    background_tasks.add_task(_scrape_source_in_background, source.id)

    logger.info("knowledge_base | funding-source refresh queued: source_id=%s by=%s", source_id, current_user.email)
    return {"status": "refresh_queued", "source_id": source_id}
