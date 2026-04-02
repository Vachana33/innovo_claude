from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import delete, func, select
from innovo_backend.shared.database import get_db
from innovo_backend.shared.models import FundingProgram, User, FundingProgramDocument, File as FileModel, FundingProgramGuidelinesSummary, funding_program_companies
from innovo_backend.shared.schemas import FundingProgramCreate, FundingProgramResponse, FundingProgramDocumentResponse, FundingProgramDocumentListResponse
from innovo_backend.shared.dependencies import get_current_user, require_admin
from innovo_backend.shared.file_storage import get_or_create_file
from innovo_backend.shared.document_extraction import extract_document_text
from innovo_backend.shared.processing_cache import get_cached_document_text
from innovo_backend.shared.funding_program_documents import detect_category_from_filename, validate_category, get_file_type_from_filename
from typing import List, Optional
import logging
import posthog

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/funding-programs", response_model=FundingProgramResponse, status_code=status.HTTP_201_CREATED)
def create_funding_program(
    program_data: FundingProgramCreate,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    require_admin(current_user)

    if not program_data.title or not program_data.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title is required")

    website_value = program_data.website.strip() if program_data.website else None
    if website_value == "":
        website_value = None

    new_program = FundingProgram(
        title=program_data.title.strip(),
        website=website_value,
        user_email=current_user.email,
    )

    try:
        db.add(new_program)
        db.commit()
        db.refresh(new_program)
        try:
            posthog.capture("funding_program_created", distinct_id=current_user.email,
                            properties={"funding_program_id": new_program.id, "title": new_program.title})
        except Exception as e:
            logger.debug("PostHog capture skipped: %s", e)
        return new_program
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to create funding program: {str(e)}") from e


@router.get("/funding-programs", response_model=List[FundingProgramResponse])
def get_funding_programs(
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    try:
        programs = db.query(FundingProgram).filter(
            FundingProgram.user_email == current_user.email
        ).order_by(FundingProgram.created_at.desc()).all()
        return programs
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to fetch funding programs: {str(e)}") from e


@router.put("/funding-programs/{funding_program_id}", response_model=FundingProgramResponse)
def update_funding_program(
    funding_program_id: int,
    program_data: FundingProgramCreate,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    require_admin(current_user)

    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email,
    ).first()
    if not funding_program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funding program not found")

    if not program_data.title or not program_data.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title is required")

    funding_program.title = program_data.title.strip()
    website_value = program_data.website.strip() if program_data.website else None
    if website_value == "":
        website_value = None
    funding_program.website = website_value

    try:
        db.commit()
        db.refresh(funding_program)
        return funding_program
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to update funding program") from None


@router.delete("/funding-programs/{funding_program_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_funding_program(
    funding_program_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    require_admin(current_user)

    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email,
    ).first()
    if not funding_program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funding program not found")

    linked_companies_count = db.execute(
        select(func.count()).select_from(funding_program_companies).where(
            funding_program_companies.c.funding_program_id == funding_program_id
        )
    ).scalar() or 0

    if linked_companies_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cannot delete funding program because companies are linked to it.")

    try:
        db.query(FundingProgramDocument).filter(
            FundingProgramDocument.funding_program_id == funding_program_id
        ).delete()
        db.query(FundingProgramGuidelinesSummary).filter(
            FundingProgramGuidelinesSummary.funding_program_id == funding_program_id
        ).delete()
        db.query(FundingProgram).filter(FundingProgram.id == funding_program_id).delete()
        db.commit()
        try:
            posthog.capture("funding_program_deleted", distinct_id=current_user.email,
                            properties={"funding_program_id": funding_program_id})
        except Exception as e:
            logger.debug("PostHog capture skipped: %s", e)
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to delete funding program: {str(e)}") from e


@router.post("/funding-programs/{funding_program_id}/guidelines/upload",
             response_model=List[FundingProgramDocumentResponse])
async def upload_funding_program_guidelines(
    funding_program_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    require_admin(current_user)
    from innovo_backend.shared.guidelines_processing import process_guidelines_for_funding_program  # noqa: PLC0415
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email,
    ).first()
    if not funding_program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funding program not found")
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    uploaded_documents = []
    try:
        for file in files:
            content = await file.read()
            file_type = get_file_type_from_filename(file.filename or "unknown")
            if file_type not in ["pdf", "docx"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Unsupported file type: {file_type}. Only PDF and DOCX files are allowed.")
            file_record, _ = get_or_create_file(db=db, file_bytes=content, file_type=file_type, filename=file.filename)
            extract_document_text(file_bytes=content, file_content_hash=file_record.content_hash,
                                  file_type=file_type, db=db)
            program_document = FundingProgramDocument(
                funding_program_id=funding_program_id, file_id=file_record.id,
                category="guidelines", original_filename=file.filename or "unknown",
                uploaded_by=current_user.email,
            )
            db.add(program_document)
            uploaded_documents.append(program_document)
        db.commit()
        for doc in uploaded_documents:
            db.refresh(doc)
        try:
            process_guidelines_for_funding_program(funding_program_id, db)
        except Exception as e:
            logger.error(f"Error processing guidelines for funding_program_id={funding_program_id}: {str(e)}")

        response_docs = []
        for doc in uploaded_documents:
            fr = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
            has_text = get_cached_document_text(db, fr.content_hash) is not None if fr else False
            response_docs.append(FundingProgramDocumentResponse(
                id=str(doc.id), funding_program_id=doc.funding_program_id, file_id=str(doc.file_id),
                category=doc.category, original_filename=doc.original_filename,
                display_name=doc.display_name, uploaded_at=doc.uploaded_at,
                file_type=fr.file_type if fr else "unknown",
                file_size=fr.size_bytes if fr else 0, has_extracted_text=has_text,
            ))
        return response_docs
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to upload guidelines: {str(e)}") from e


@router.get("/funding-programs/{funding_program_id}/documents",
            response_model=FundingProgramDocumentListResponse)
def get_funding_program_documents(
    funding_program_id: int,
    category: Optional[str] = None,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    require_admin(current_user)
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email,
    ).first()
    if not funding_program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funding program not found")

    query = db.query(FundingProgramDocument).filter(
        FundingProgramDocument.funding_program_id == funding_program_id
    )
    if category and validate_category(category):
        query = query.filter(FundingProgramDocument.category == category)
    documents = query.all()

    response_docs = []
    category_counts: dict = {}
    for doc in documents:
        fr = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
        has_text = get_cached_document_text(db, fr.content_hash) is not None if fr and fr.file_type in ["pdf", "docx"] else (fr.file_type == "txt" if fr else False)
        response_docs.append(FundingProgramDocumentResponse(
            id=str(doc.id), funding_program_id=doc.funding_program_id, file_id=str(doc.file_id),
            category=doc.category, original_filename=doc.original_filename,
            display_name=doc.display_name, uploaded_at=doc.uploaded_at,
            file_type=fr.file_type if fr else "unknown",
            file_size=fr.size_bytes if fr else 0, has_extracted_text=has_text,
        ))
        category_counts[doc.category] = category_counts.get(doc.category, 0) + 1
    return FundingProgramDocumentListResponse(documents=response_docs, categories=category_counts)


@router.delete("/funding-programs/{funding_program_id}/documents/{document_id}")
def delete_funding_program_document(
    funding_program_id: int,
    document_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    require_admin(current_user)
    from innovo_backend.shared.guidelines_processing import process_guidelines_for_funding_program  # noqa: PLC0415
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email,
    ).first()
    if not funding_program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funding program not found")

    document = db.query(FundingProgramDocument).filter(
        FundingProgramDocument.id == document_id,
        FundingProgramDocument.funding_program_id == funding_program_id,
    ).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    db.delete(document)
    db.commit()

    if document.category == "guidelines":
        try:
            process_guidelines_for_funding_program(funding_program_id, db)
        except Exception as e:
            logger.error(f"Error reprocessing guidelines after deletion: {str(e)}")

    return {"message": "Document deleted successfully"}
