from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import delete, func, select
from app.database import get_db
from app.models import FundingProgram, User, FundingProgramDocument, File as FileModel, FundingProgramGuidelinesSummary, funding_program_companies
from app.guidelines_processing import process_guidelines_for_funding_program
from app.schemas import FundingProgramCreate, FundingProgramResponse, FundingProgramDocumentResponse, FundingProgramDocumentListResponse
from app.dependencies import get_current_user
from app.file_storage import get_or_create_file
from app.document_extraction import extract_document_text
from app.processing_cache import get_cached_document_text
from app.funding_program_documents import detect_category_from_filename, validate_category, get_file_type_from_filename, is_text_file
from typing import List, Optional
import logging
import posthog

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/funding-programs", response_model=FundingProgramResponse, status_code=status.HTTP_201_CREATED)
def create_funding_program(
    program_data: FundingProgramCreate,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Create a new funding program.
    """
    if not program_data.title or not program_data.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Title is required"
        )

    # Create new funding program (owned by current user)
    # Handle empty website string - convert to None
    website_value = program_data.website.strip() if program_data.website else None
    if website_value == "":
        website_value = None

    new_program = FundingProgram(
        title=program_data.title.strip(),
        website=website_value,
        user_email=current_user.email
    )

    try:
        db.add(new_program)
        db.commit()
        db.refresh(new_program)

        try:
            posthog.capture(
                "funding_program_created",
                distinct_id=current_user.email,
                properties={
                    "funding_program_id": new_program.id,
                    "title": new_program.title,
                    "has_website": bool(new_program.website),
                },
            )
        except Exception as e:
            logger.debug("PostHog capture skipped: %s", e)
        return new_program
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating funding program: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create funding program: {str(e)}"
        ) from e

@router.get("/funding-programs", response_model=List[FundingProgramResponse])
def get_funding_programs(
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Get all funding programs owned by the current user.
    """
    try:
        programs = db.query(FundingProgram).filter(
            FundingProgram.user_email == current_user.email
        ).order_by(FundingProgram.created_at.desc()).all()
        logger.info(f"Retrieved {len(programs)} funding programs for user {current_user.email}")
        return programs
    except Exception as e:
        logger.error(f"Error fetching funding programs for user {current_user.email}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch funding programs: {str(e)}"
        ) from e

@router.put("/funding-programs/{funding_program_id}", response_model=FundingProgramResponse)
def update_funding_program(
    funding_program_id: int,
    program_data: FundingProgramCreate,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Update an existing funding program.
    """
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email
    ).first()
    if not funding_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funding program not found"
        )

    if not program_data.title or not program_data.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Title is required"
        )

    # Update funding program
    funding_program.title = program_data.title.strip()
    # Handle empty website string - convert to None
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update funding program"
        ) from None

@router.delete("/funding-programs/{funding_program_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_funding_program(
    funding_program_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Delete a funding program.
    """
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email
    ).first()
    if not funding_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funding program not found"
        )

    # Check if any companies are linked to this funding program
    linked_companies_count = db.execute(
        select(func.count()).select_from(funding_program_companies).where(
            funding_program_companies.c.funding_program_id == funding_program_id
        )
    ).scalar() or 0
    
    if linked_companies_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete funding program because companies are linked to it."
        )

    try:
        # #region agent log
        logger.info(f"[DELETE] Starting deletion of funding_program_id={funding_program_id}")
        # #endregion
        
        # Delete all related funding_program_documents
        try:
            docs_deleted = db.query(FundingProgramDocument).filter(
                FundingProgramDocument.funding_program_id == funding_program_id
            ).delete()
            # #region agent log
            logger.info(f"[DELETE] Deleted {docs_deleted} funding_program_documents")
            # #endregion
        except Exception as docs_error:
            # #region agent log
            logger.error(f"[DELETE] Error deleting documents: {str(docs_error)}")
            # #endregion
            db.rollback()
            raise
        
        # Delete guidelines summary if exists
        try:
            summary_deleted = db.query(FundingProgramGuidelinesSummary).filter(
                FundingProgramGuidelinesSummary.funding_program_id == funding_program_id
            ).delete()
            # #region agent log
            logger.info(f"[DELETE] Deleted {summary_deleted} guidelines_summary records")
            # #endregion
        except Exception as summary_error:
            # #region agent log
            logger.warning(f"[DELETE] Error deleting guidelines_summary (may not exist): {str(summary_error)}")
            # #endregion
            # Check if it's a table doesn't exist error - if so, continue; otherwise rollback
            error_str = str(summary_error).lower()
            if "does not exist" not in error_str and "no such table" not in error_str and "relation" not in error_str:
                # Real error - rollback and raise
                db.rollback()
                raise
        
        # Delete the funding program itself using direct query to avoid relationship access
        # This prevents SQLAlchemy from trying to lazy-load the companies relationship
        program_deleted = db.query(FundingProgram).filter(
            FundingProgram.id == funding_program_id
        ).delete()
        # #region agent log
        logger.info(f"[DELETE] Deleted {program_deleted} funding_program record, committing...")
        # #endregion

        db.commit()
        # #region agent log
        logger.info(f"[DELETE] Successfully deleted funding_program_id={funding_program_id}")
        # #endregion
        try:
            posthog.capture(
                "funding_program_deleted",
                distinct_id=current_user.email,
                properties={"funding_program_id": funding_program_id},
            )
        except Exception as e:
            logger.debug("PostHog capture skipped: %s", e)
        return None
    except Exception as e:
        # #region agent log
        logger.error(f"[DELETE] Error deleting funding_program_id={funding_program_id}: {str(e)}", exc_info=True)
        # #endregion
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete funding program: {str(e)}"
        ) from e



# Phase 4: Funding Program Document Ingestion Endpoints

@router.post("/funding-programs/{funding_program_id}/guidelines/upload", response_model=List[FundingProgramDocumentResponse])
async def upload_funding_program_guidelines(
    funding_program_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Upload multiple guidelines documents (PDFs, DOCX) for a funding program.
    
    - Accepts: PDF, DOCX files
    - Category: Automatically set to "guidelines"
    - Extracts text and stores in DocumentTextCache
    - Returns list of uploaded documents with their IDs
    """
    # Verify funding program exists and user owns it
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email
    ).first()

    if not funding_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funding program not found"
        )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )

    uploaded_documents = []

    try:
        for file in files:
            # Read file content
            content = await file.read()

            # Determine file type
            file_type = get_file_type_from_filename(file.filename or "unknown")

            # Validate file type - only PDF and DOCX allowed
            if file_type not in ["pdf", "docx"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file type: {file_type}. Only PDF and DOCX files are allowed."
                )

            # Get or create file record (hash-based deduplication)
            file_record, is_new = get_or_create_file(
                db=db,
                file_bytes=content,
                file_type=file_type,
                filename=file.filename
            )

            # Extract text for PDFs/DOCX (uses existing caching)
            _ = extract_document_text(
                file_bytes=content,
                file_content_hash=file_record.content_hash,
                file_type=file_type,
                db=db
            )

            # Create FundingProgramDocument record with category="guidelines"
            program_document = FundingProgramDocument(
                funding_program_id=funding_program_id,
                file_id=file_record.id,
                category="guidelines",
                original_filename=file.filename or "unknown",
                uploaded_by=current_user.email
            )

            db.add(program_document)
            uploaded_documents.append(program_document)

            logger.info(f"Uploaded guidelines document: {file.filename} (file_type: {file_type})")

        db.commit()

        # Refresh documents to get IDs
        for doc in uploaded_documents:
            db.refresh(doc)

        # Process guidelines and generate rules summary
        try:
            process_guidelines_for_funding_program(funding_program_id, db)
        except Exception as e:
            logger.error(f"Error processing guidelines for funding_program_id={funding_program_id}: {str(e)}")
            # Don't fail the upload if processing fails

        # Build response
        response_docs = []
        for doc in uploaded_documents:
            file_record = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
            has_text = False
            if file_record:
                cached_text = get_cached_document_text(db, file_record.content_hash)
                has_text = cached_text is not None

            response_docs.append(FundingProgramDocumentResponse(
                id=str(doc.id),
                funding_program_id=doc.funding_program_id,
                file_id=str(doc.file_id),
                category=doc.category,
                original_filename=doc.original_filename,
                display_name=doc.display_name,
                uploaded_at=doc.uploaded_at,
                file_type=file_record.file_type if file_record else "unknown",
                file_size=file_record.size_bytes if file_record else 0,
                has_extracted_text=has_text
            ))

        return response_docs

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading guidelines for funding_program_id={funding_program_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload guidelines: {str(e)}"
        ) from e


@router.post("/funding-programs/{funding_program_id}/documents/upload", response_model=List[FundingProgramDocumentResponse])
async def upload_funding_program_documents(
    funding_program_id: int,
    files: List[UploadFile] = File(...),
    category: Optional[str] = None,  # Optional category override
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Upload multiple documents (PDFs, DOCX) for a funding program.

    - PDFs/DOCX: Extracted and stored in DocumentTextCache
    - Auto-organizes by folder structure if category not provided
    - Returns list of uploaded documents with their IDs
    """
    # Verify funding program exists and user owns it
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email
    ).first()

    if not funding_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funding program not found"
        )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )

    uploaded_documents = []

    try:
        for file in files:
            # Read file content
            content = await file.read()

            # Determine file type
            file_type = get_file_type_from_filename(file.filename or "unknown")

            # Validate file type - only PDF and DOCX allowed
            if file_type not in ["pdf", "docx"]:
                logger.warning(f"Skipping unsupported file type: {file_type} for {file.filename}")
                continue

            # Get or create file record (hash-based deduplication)
            file_record, is_new = get_or_create_file(
                db=db,
                file_bytes=content,
                file_type=file_type,
                filename=file.filename
            )

            # Determine category
            detected_category = category if category and validate_category(category) else detect_category_from_filename(file.filename or "")
            if not validate_category(detected_category):
                detected_category = "guidelines"  # Fallback

            # Extract text for PDFs/DOCX (uses existing caching)
            # The extraction triggers caching - result not needed here
            if file_type in ["pdf", "docx"]:
                _ = extract_document_text(
                    file_bytes=content,
                    file_content_hash=file_record.content_hash,
                    file_type=file_type,
                    db=db
                )

            # Create FundingProgramDocument record
            program_document = FundingProgramDocument(
                funding_program_id=funding_program_id,
                file_id=file_record.id,
                category=detected_category,
                original_filename=file.filename or "unknown",
                uploaded_by=current_user.email
            )

            db.add(program_document)
            uploaded_documents.append(program_document)

            logger.info(f"Uploaded document: {file.filename} (category: {detected_category}, file_type: {file_type})")

        db.commit()

        # Refresh documents to get IDs
        for doc in uploaded_documents:
            db.refresh(doc)

        # Build response
        response_docs = []
        for doc in uploaded_documents:
            file_record = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
            has_text = False
            if file_record:
                if file_record.file_type in ["pdf", "docx"]:
                    cached_text = get_cached_document_text(db, file_record.content_hash)
                    has_text = cached_text is not None
                elif file_record.file_type == "txt":
                    has_text = True

            response_docs.append(FundingProgramDocumentResponse(
                id=str(doc.id),
                funding_program_id=doc.funding_program_id,
                file_id=str(doc.file_id),
                category=doc.category,
                original_filename=doc.original_filename,
                display_name=doc.display_name,
                uploaded_at=doc.uploaded_at,
                file_type=file_record.file_type if file_record else "unknown",
                file_size=file_record.size_bytes if file_record else 0,
                has_extracted_text=has_text
            ))

        return response_docs

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading documents for funding_program_id={funding_program_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload documents: {str(e)}"
        ) from e


@router.get("/funding-programs/{funding_program_id}/documents", response_model=FundingProgramDocumentListResponse)
def get_funding_program_documents(
    funding_program_id: int,
    category: Optional[str] = None,  # Filter by category
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Get all documents for a funding program, optionally filtered by category.
    Returns document metadata including extracted text preview.
    """
    # Verify funding program exists and user owns it
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email
    ).first()

    if not funding_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funding program not found"
        )

    # Build query
    query = db.query(FundingProgramDocument).filter(
        FundingProgramDocument.funding_program_id == funding_program_id
    )

    # Filter by category if provided
    if category and validate_category(category):
        query = query.filter(FundingProgramDocument.category == category)

    documents = query.all()

    # Build response
    response_docs = []
    category_counts = {}

    for doc in documents:
        file_record = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
        has_text = False
        if file_record:
            if file_record.file_type in ["pdf", "docx"]:
                cached_text = get_cached_document_text(db, file_record.content_hash)
                has_text = cached_text is not None
            elif file_record.file_type == "txt":
                has_text = True

        response_docs.append(FundingProgramDocumentResponse(
            id=str(doc.id),
            funding_program_id=doc.funding_program_id,
            file_id=str(doc.file_id),
            category=doc.category,
            original_filename=doc.original_filename,
            display_name=doc.display_name,
            uploaded_at=doc.uploaded_at,
            file_type=file_record.file_type if file_record else "unknown",
            file_size=file_record.size_bytes if file_record else 0,
            has_extracted_text=has_text
        ))

        # Count by category
        category_counts[doc.category] = category_counts.get(doc.category, 0) + 1

    return FundingProgramDocumentListResponse(
        documents=response_docs,
        categories=category_counts
    )


@router.get("/funding-programs/{funding_program_id}/documents/{document_id}/text")
def get_document_text(
    funding_program_id: int,
    document_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Get extracted text for a specific document.
    Uses DocumentTextCache for efficient retrieval.
    """
    # Verify funding program exists and user owns it
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email
    ).first()

    if not funding_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funding program not found"
        )

    # Get document
    document = db.query(FundingProgramDocument).filter(
        FundingProgramDocument.id == document_id,
        FundingProgramDocument.funding_program_id == funding_program_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Get file record
    file_record = db.query(FileModel).filter(FileModel.id == document.file_id).first()

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File record not found"
        )

    # Get text based on file type
    if file_record.file_type == "txt":
        # For text files, read from file storage
        # Note: Text files should be stored in Supabase Storage, not in database
        # For now, return error - text files should be PDF/DOCX for extraction
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text file extraction not supported. Please use PDF or DOCX files."
        )
    elif file_record.file_type in ["pdf", "docx"]:
        # For PDFs/DOCX, get from cache
        extracted_text = get_cached_document_text(db, file_record.content_hash)
        if extracted_text:
            return {"text": extracted_text, "source": "document_text_cache"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Extracted text not found. Document may not have been processed yet."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_record.file_type} does not support text extraction"
        )


@router.delete("/funding-programs/{funding_program_id}/documents/{document_id}")
def delete_funding_program_document(
    funding_program_id: int,
    document_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Delete a funding program document.
    Note: File record and storage remain (may be used by other documents).
    """
    # Verify funding program exists and user owns it
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email
    ).first()

    if not funding_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funding program not found"
        )

    # Get document
    document = db.query(FundingProgramDocument).filter(
        FundingProgramDocument.id == document_id,
        FundingProgramDocument.funding_program_id == funding_program_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Delete document record
    db.delete(document)
    db.commit()

    # Reprocess guidelines if this was a guidelines document
    if document.category == "guidelines":
        try:
            process_guidelines_for_funding_program(funding_program_id, db)
        except Exception as e:
            logger.error(f"Error reprocessing guidelines after deletion for funding_program_id={funding_program_id}: {str(e)}")
            # Don't fail the deletion if processing fails

    logger.info(f"Deleted funding program document: {document_id}")

    return {"message": "Document deleted successfully"}
