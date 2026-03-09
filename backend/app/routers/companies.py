from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models import FundingProgram, Company, Document, funding_program_companies, User, CompanyDocument
from app.schemas import CompanyCreate, CompanyResponse, CompanyDocumentResponse, CompanyDocumentListResponse
from app.preprocessing import crawl_website, transcribe_audio
from app.extraction import extract_company_profile
from app.dependencies import get_current_user
from app.file_storage import get_or_create_file, get_file_by_id, download_from_supabase_storage, compute_file_hash
from app.audio_compression import compress_audio, validate_audio_size
from app.models import File as FileModel
from app.document_extraction import extract_document_text
from app.processing_cache import get_cached_document_text
from app.funding_program_documents import get_file_type_from_filename
from typing import List
from datetime import datetime, timezone
import logging
import os
import posthog

from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()

# UPLOAD_DIR configuration - environment-driven for production persistence
# Default: backend/uploads/audio (local dev)
# Production: Set UPLOAD_DIR environment variable (e.g., /var/data/uploads)
UPLOAD_DIR_ENV = os.getenv("UPLOAD_DIR")
if UPLOAD_DIR_ENV:
    # Production: use environment-provided base directory
    UPLOAD_DIR = Path(UPLOAD_DIR_ENV) / "audio"
else:
    # Local dev: default to backend/uploads/audio
    UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "audio"

# Create uploads directory if it doesn't exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload-audio")
async def upload_audio_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Upload an audio file with hash-based deduplication and automatic compression.
    
    Features:
    - Validates file size (max 45MB before compression)
    - Automatically compresses audio for speech-to-text (mono, 16kHz, low bitrate)
    - Returns file_id instead of raw path
    
    Returns:
        file_id, audio_path (same as file_id for backward compatibility), filename, is_new
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an audio file"
            )

        # Read file content
        original_content = await file.read()
        
        # Validate file size before processing
        is_valid, error_message = validate_audio_size(original_content)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=error_message
            )
        
        # Check if file already exists by hash (before compression)
        # This allows reusing existing files without re-compressing
        original_hash = compute_file_hash(original_content)
        existing_file = db.query(FileModel).filter(FileModel.content_hash == original_hash).first()
        
        if existing_file:
            logger.info(f"Audio file already exists (file_id={existing_file.id}, hash={original_hash}), reusing")
            return {
                "file_id": existing_file.id,
                "audio_path": existing_file.id,
                "filename": file.filename,
                "is_new": False
            }
        
        # File doesn't exist, proceed with compression and upload
        # Determine input format from filename or content type
        input_format = "m4a"  # Default
        if file.filename:
            ext = Path(file.filename).suffix.lower().lstrip('.')
            if ext in ["mp3", "wav", "m4a", "aac", "ogg", "flac"]:
                input_format = ext
        
        # Compress audio for speech-to-text processing
        # Compression reduces file size while maintaining speech quality
        compressed_content = compress_audio(original_content, input_format=input_format)
        
        if not compressed_content:
            logger.warning("Audio compression failed, using original file")
            compressed_content = original_content
        else:
            # Validate compressed file size (should be smaller, but check anyway)
            is_valid_compressed, error_msg = validate_audio_size(compressed_content)
            if not is_valid_compressed:
                logger.warning(f"Compressed file still too large: {error_msg}, using original")
                compressed_content = original_content
        
        # Check if compressed version already exists
        compressed_hash = compute_file_hash(compressed_content)
        existing_compressed_file = db.query(FileModel).filter(FileModel.content_hash == compressed_hash).first()
        
        if existing_compressed_file:
            logger.info(f"Compressed audio file already exists (file_id={existing_compressed_file.id}), reusing")
            return {
                "file_id": existing_compressed_file.id,
                "audio_path": existing_compressed_file.id,
                "filename": file.filename,
                "is_new": False
            }

        # Get or create file record (hash-based deduplication)
        # Use compressed content for storage to save space
        file_record, is_new = get_or_create_file(
            db=db,
            file_bytes=compressed_content,
            file_type="audio",
            filename=file.filename
        )

        db.commit()

        logger.info(
            f"Audio file {'uploaded' if is_new else 'reused'} "
            f"(file_id={file_record.id}, original_size={len(original_content)} bytes, "
            f"stored_size={len(compressed_content)} bytes)"
        )

        # Return file_id as audio_path for backward compatibility with frontend
        # Frontend expects audio_path, so we use file_id as the value
        # Backend processing will detect if it's a file_id (UUID) or legacy path
        return {
            "file_id": file_record.id,
            "audio_path": file_record.id,  # Return file_id as audio_path for backward compatibility
            "filename": file.filename,
            "is_new": is_new
        }

    except HTTPException:
        # Re-raise HTTP exceptions (like 413) as-is
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading audio file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload audio file: {str(e)}"
        ) from e

def process_company_background(company_id: int, website: str = None, audio_path: str = None):
    """
    Background task to process company data (website crawling and audio transcription).
    This runs asynchronously after the API response is returned.
    """
    from app.database import SessionLocal

    db = None
    try:
        db = SessionLocal()
        # Log preprocessing start
        logger.info(f"Starting preprocessing for company_id={company_id}")

        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            logger.error(f"Company not found for preprocessing: company_id={company_id}")
            return

        # Update status to processing
        company.processing_status = "processing"
        company.processing_error = None
        db.commit()

        # Process website
        if website:
            try:
                logger.info(f"Extracting website data for company_id={company_id} (url={website})")
                # Use new About page scraping
                from app.website_scraping import scrape_about_page
                from app.text_cleaning import clean_website_text
                
                website_raw, _ = scrape_about_page(website, db=db)
                if website_raw:
                    company.website_raw_text = website_raw
                    # Clean the website text
                    website_clean = clean_website_text(website_raw)
                    company.website_clean_text = website_clean
                    # Keep legacy field for backward compatibility
                    company.website_text = website_clean
                    logger.info(f"Website data extraction completed for company_id={company_id} (raw: {len(website_raw)} chars, clean: {len(website_clean)} chars)")
                else:
                    logger.warning(f"Website data extraction returned no text for company_id={company_id}")
            except Exception as e:
                error_msg = f"Website crawl failed: {str(e)}"
                logger.error(f"Website data extraction failed for company_id={company_id}: {error_msg}")
                company.processing_error = error_msg

        # Process audio
        if audio_path:
            try:
                # Check if audio_path is a file_id (UUID format) or legacy path
                # UUID format: 36 characters with hyphens
                is_file_id = len(audio_path) == 36 and audio_path.count('-') == 4

                if is_file_id:
                    # New: file_id approach - get file from database and download from Supabase
                    logger.info(f"Processing audio via file_id for company_id={company_id} (file_id={audio_path})")
                    file_record = get_file_by_id(db, audio_path)
                    if not file_record:
                        raise Exception(f"File not found: file_id={audio_path}")

                    # Download file from Supabase Storage
                    file_bytes = download_from_supabase_storage(file_record.storage_path)
                    if not file_bytes:
                        raise Exception(f"Failed to download file from Supabase Storage: {file_record.storage_path}")

                    # Save to temporary file for transcription (OpenAI Whisper requires file path)
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.m4a') as tmp_file:
                        tmp_file.write(file_bytes)
                        tmp_audio_path = tmp_file.name

                    try:
                        logger.info(f"Transcribing audio for company_id={company_id} (file_id={audio_path})")
                        # Phase 2: Pass file_content_hash and db session for cache lookup/storage
                        transcript_raw = transcribe_audio(
                            tmp_audio_path,
                            file_content_hash=file_record.content_hash,
                            db=db
                        )
                        if transcript_raw:
                            company.transcript_raw = transcript_raw
                            # Clean the transcript
                            from app.text_cleaning import clean_transcript
                            transcript_clean = clean_transcript(transcript_raw)
                            company.transcript_clean = transcript_clean
                            # Keep legacy field for backward compatibility
                            company.transcript_text = transcript_clean
                            logger.info(f"Audio transcription completed for company_id={company_id} (raw: {len(transcript_raw)} chars, clean: {len(transcript_clean)} chars)")
                        else:
                            logger.warning(f"Audio transcription returned no text for company_id={company_id}")
                    finally:
                        # Clean up temporary file
                        if os.path.exists(tmp_audio_path):
                            os.unlink(tmp_audio_path)
                else:
                    # Legacy: filename path approach (backward compatibility)
                    # Resolve audio path relative to UPLOAD_DIR
                    if os.path.isabs(audio_path):
                        # Legacy: absolute path (backward compatibility)
                        resolved_audio_path = audio_path
                    else:
                        # Legacy: filename relative to UPLOAD_DIR
                        resolved_audio_path = str(UPLOAD_DIR / audio_path)

                    logger.info(f"Transcribing audio for company_id={company_id} (legacy audio_path={resolved_audio_path})")
                    # Phase 2: For legacy paths, we don't have content_hash, so cache won't be used
                    # Pass db session anyway in case we want to add hash computation for legacy files later
                    transcript_raw = transcribe_audio(resolved_audio_path, file_content_hash=None, db=db)
                    if transcript_raw:
                        company.transcript_raw = transcript_raw
                        # Clean the transcript
                        from app.text_cleaning import clean_transcript
                        transcript_clean = clean_transcript(transcript_raw)
                        company.transcript_clean = transcript_clean
                        # Keep legacy field for backward compatibility
                        company.transcript_text = transcript_clean
                        logger.info(f"Audio transcription completed for company_id={company_id} (raw: {len(transcript_raw)} chars, clean: {len(transcript_clean)} chars)")
                    else:
                        logger.warning(f"Audio transcription returned no text for company_id={company_id}")
            except Exception as e:
                error_msg = f"Audio transcription failed: {str(e)}"
                logger.error(f"Audio transcription failed for company_id={company_id}: {error_msg}")
                if company.processing_error:
                    company.processing_error += f"; {error_msg}"
                else:
                    company.processing_error = error_msg

        # Update status to done (website/audio processing complete)
        company.processing_status = "done"
        company.updated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Finished preprocessing for company_id={company_id}")

        # Phase 2C: Extract structured company profile
        # Only run extraction if we have text data and haven't extracted yet
        has_text_data = (company.website_text and company.website_text.strip()) or (company.transcript_text and company.transcript_text.strip())
        already_extracted = company.extraction_status == "extracted"

        if has_text_data and not already_extracted:
            try:
                logger.info(f"Starting structured profile extraction for company_id={company_id}")

                # Update extraction status to processing
                company.extraction_status = "pending"
                db.commit()

                # Extract structured profile from raw text
                website_text = company.website_text or ""
                transcript_text = company.transcript_text or ""

                company_profile = extract_company_profile(website_text, transcript_text)

                # Store extracted profile
                company.company_profile = company_profile
                company.extraction_status = "extracted"
                company.extracted_at = datetime.now(timezone.utc)
                db.commit()

                logger.info(f"Structured profile extraction completed for company_id={company_id}")

            except Exception as e:
                # Extraction failed - mark as failed but don't fail the entire preprocessing
                error_msg = f"Profile extraction failed: {str(e)}"
                logger.error(f"Profile extraction failed for company_id={company_id}: {error_msg}")

                try:
                    company.extraction_status = "failed"
                    # Don't set extracted_at if extraction failed
                    db.commit()
                except Exception as commit_error:
                    logger.error(f"Failed to update extraction error status for company_id={company_id}: {str(commit_error)}")
        elif already_extracted:
            logger.info(f"Skipping extraction for company_id={company_id} - already extracted")
        elif not has_text_data:
            logger.info(f"Skipping extraction for company_id={company_id} - no text data available")

    except Exception as e:
        logger.error(f"Preprocessing failed for company_id={company_id}: {str(e)}")
        # Only attempt to update error status if database session is available
        if db is not None:
            try:
                company = db.query(Company).filter(Company.id == company_id).first()
                if company:
                    company.processing_status = "failed"
                    company.processing_error = f"Background processing error: {str(e)}"
                    db.commit()
            except Exception as commit_error:
                logger.error(f"Failed to update error status for company_id={company_id}: {str(commit_error)}")
        else:
            logger.error(f"Cannot update error status for company_id={company_id}: database session not available")
    finally:
        # Ensure database session is always closed to prevent connection leaks
        if db is not None:
            try:
                db.close()
            except Exception as close_error:
                logger.error(f"Failed to close database session for company_id={company_id}: {str(close_error)}")


@router.post(
    "/funding-programs/{funding_program_id}/companies",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED
)
def create_company_in_program(
    funding_program_id: int,
    company_data: CompanyCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Create a new company and automatically link it to the given funding program.
    Background processing (website crawling and audio transcription) is triggered
    after the response is returned.

    Note: For file uploads, use the /upload-audio endpoint first, then provide the audio_path.
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

    if not company_data.name or not company_data.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company name is required"
        )

    # Create new company with initial processing status (owned by current user)
    # Note: audio_path can now be either a file_id (UUID) or legacy path string
    new_company = Company(
        name=company_data.name.strip(),
        website=company_data.website.strip() if company_data.website else None,
        audio_path=company_data.audio_path.strip() if company_data.audio_path else None,  # Can be file_id or legacy path
        processing_status="pending",
        user_email=current_user.email
    )

    try:
        db.add(new_company)
        db.flush()  # Flush to get the company ID

        # Refresh funding_program to ensure we have latest state
        db.refresh(funding_program)

        # Link company to funding program
        # Check if link already exists to avoid UNIQUE constraint violation
        # Check both via relationship and direct query for safety
        company_already_linked = new_company in funding_program.companies

        if not company_already_linked:
            # Double-check with direct query
            existing_link = db.execute(
                select(funding_program_companies).where(
                    funding_program_companies.c.funding_program_id == funding_program_id,
                    funding_program_companies.c.company_id == new_company.id
                )
            ).first()

            if not existing_link:
                funding_program.companies.append(new_company)

        db.commit()
        db.refresh(new_company)

        try:
            posthog.capture(
                "company_created",
                distinct_id=current_user.email,
                properties={
                    "company_id": new_company.id,
                    "company_name": new_company.name,
                    "funding_program_id": funding_program_id,
                    "has_website": bool(new_company.website),
                    "has_audio": bool(new_company.audio_path),
                },
            )
        except Exception as e:
            logger.debug("PostHog capture skipped: %s", e)

        # Schedule background processing
        if new_company.website or new_company.audio_path:
            background_tasks.add_task(
                process_company_background,
                company_id=new_company.id,
                website=new_company.website,
                audio_path=new_company.audio_path
            )
            logger.info(f"Company preprocessing task enqueued for company_id={new_company.id}")

        return new_company
    except IntegrityError as e:
        db.rollback()
        # Check if it's a UNIQUE constraint on the join table
        error_str = str(e.orig) if hasattr(e, 'orig') else str(e)
        if 'funding_program_companies' in error_str and 'UNIQUE' in error_str:
            # Company link already exists - this means the company was created in a previous transaction
            # or the link already exists. Query for the company by its identifying attributes
            # (not by ID, since the rollback undid the insertion)
            logger.warning(f"Company link already exists for funding_program_id={funding_program_id}, attempting to find existing company")
            # Query for the company by name and user_email (the identifying attributes)
            existing_company = db.query(Company).filter(
                Company.name == company_data.name.strip(),
                Company.user_email == current_user.email
            ).first()
            if existing_company:
                # Ensure it's linked to the funding program
                db.refresh(funding_program)
                if existing_company not in funding_program.companies:
                    funding_program.companies.append(existing_company)
                    db.commit()
                return existing_company
        # Re-raise if it's not the join table constraint or company not found
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create company: {str(e)}"
        ) from e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create company: {str(e)}"
        ) from e

@router.get(
    "/funding-programs/{funding_program_id}/companies",
    response_model=List[CompanyResponse]
)
def get_companies_for_program(
    funding_program_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Get all companies linked to a specific funding program.
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

    # Return companies linked to this funding program (filtered by user ownership)
    # Only return companies that belong to the current user
    return [c for c in funding_program.companies if c.user_email == current_user.email]


@router.post("/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    company_data: CompanyCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Create a new company.
    Background processing (website crawling and audio transcription) is triggered
    after the response is returned.

    Note: For file uploads, use the /upload-audio endpoint first, then provide the audio_path.
    """
    if not company_data.name or not company_data.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company name is required"
        )

    # Create new company with initial processing status (owned by current user)
    # Note: audio_path can now be either a file_id (UUID) or legacy path string
    new_company = Company(
        name=company_data.name.strip(),
        website=company_data.website.strip() if company_data.website else None,
        audio_path=company_data.audio_path.strip() if company_data.audio_path else None,  # Can be file_id or legacy path
        processing_status="pending",
        user_email=current_user.email
    )

    try:
        db.add(new_company)
        db.commit()
        db.refresh(new_company)

        try:
            posthog.capture(
                "company_created",
                distinct_id=current_user.email,
                properties={
                    "company_id": new_company.id,
                    "company_name": new_company.name,
                    "has_website": bool(new_company.website),
                    "has_audio": bool(new_company.audio_path),
                },
            )
        except Exception as e:
            logger.debug("PostHog capture skipped: %s", e)

        # Schedule background processing
        if new_company.website or new_company.audio_path:
            background_tasks.add_task(
                process_company_background,
                company_id=new_company.id,
                website=new_company.website,
                audio_path=new_company.audio_path
            )
            logger.info(f"Company preprocessing task enqueued for company_id={new_company.id}")

        return new_company
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create company: {str(e)}"
        ) from e

@router.get("/companies", response_model=List[CompanyResponse])
def get_all_companies(
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Get all companies owned by the current user across all funding programs.
    Used for importing existing companies.
    """
    companies = db.query(Company).filter(
        Company.user_email == current_user.email
    ).order_by(Company.created_at.desc()).all()
    return companies

@router.get("/companies/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Get a single company by ID.
    """
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.user_email == current_user.email
    ).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    return company

@router.post(
    "/funding-programs/{funding_program_id}/companies/{company_id}",
    response_model=CompanyResponse,
    status_code=status.HTTP_200_OK
)
def import_company_to_program(
    funding_program_id: int,
    company_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Import an existing company into a funding program.
    Only creates an entry in the join table, does not create a new company.
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

    # Verify company exists and belongs to current user
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.user_email == current_user.email
    ).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    # Check if company is already linked to this funding program
    if company in funding_program.companies:
        # Company already linked, return it
        return company

    try:
        # Link existing company to funding program
        funding_program.companies.append(company)
        db.commit()
        db.refresh(company)
        return company
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import company: {str(e)}"
        ) from e

@router.put("/companies/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    company_data: CompanyCreate,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Update an existing company.
    """
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.user_email == current_user.email
    ).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    if not company_data.name or not company_data.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company name is required"
        )

    # Update company
    company.name = company_data.name.strip()
    company.website = company_data.website.strip() if company_data.website else None
    company.audio_path = company_data.audio_path.strip() if company_data.audio_path else None

    try:
        db.commit()
        db.refresh(company)
        return company
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update company"
        ) from e

@router.delete("/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Delete a company.
    This removes the company from the database entirely.
    """
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.user_email == current_user.email
    ).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    try:
        # Delete all related documents first
        db.query(Document).filter(Document.company_id == company_id).delete()

        # Delete all join table entries (funding_program_companies)
        db.execute(
            delete(funding_program_companies).where(
                funding_program_companies.c.company_id == company_id
            )
        )

        # Delete the company itself
        db.delete(company)
        db.commit()
        try:
            posthog.capture(
                "company_deleted",
                distinct_id=current_user.email,
                properties={"company_id": company_id},
            )
        except Exception as e:
            logger.debug("PostHog capture skipped: %s", e)
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete company"
        ) from e


# Company Document Upload Endpoints

@router.post("/companies/{company_id}/documents/upload", response_model=List[CompanyDocumentResponse])
async def upload_company_documents(
    company_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Upload multiple documents (PDFs, DOCX) for a company.
    
    - Accepts: PDF, DOCX files
    - Extracts text and stores in DocumentTextCache
    - Returns list of uploaded documents with their IDs
    """
    # Verify company exists and user owns it
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.user_email == current_user.email
    ).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
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

            # Create CompanyDocument record
            company_document = CompanyDocument(
                company_id=company_id,
                file_id=file_record.id,
                original_filename=file.filename or "unknown",
                uploaded_by=current_user.email
            )

            db.add(company_document)
            uploaded_documents.append(company_document)

            logger.info(f"Uploaded company document: {file.filename} (file_type: {file_type})")

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

            response_docs.append(CompanyDocumentResponse(
                id=str(doc.id),
                company_id=doc.company_id,
                file_id=str(doc.file_id),
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
        logger.error(f"Error uploading documents for company_id={company_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload documents: {str(e)}"
        ) from e


@router.get("/companies/{company_id}/documents", response_model=CompanyDocumentListResponse)
def get_company_documents(
    company_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Get all documents for a company.
    Returns document metadata including extracted text preview.
    """
    # Verify company exists and user owns it
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.user_email == current_user.email
    ).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    documents = db.query(CompanyDocument).filter(
        CompanyDocument.company_id == company_id
    ).all()

    # Build response
    response_docs = []
    for doc in documents:
        file_record = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
        has_text = False
        if file_record:
            if file_record.file_type in ["pdf", "docx"]:
                cached_text = get_cached_document_text(db, file_record.content_hash)
                has_text = cached_text is not None
            elif file_record.file_type == "txt":
                has_text = True

        response_docs.append(CompanyDocumentResponse(
            id=str(doc.id),
            company_id=doc.company_id,
            file_id=str(doc.file_id),
            original_filename=doc.original_filename,
            display_name=doc.display_name,
            uploaded_at=doc.uploaded_at,
            file_type=file_record.file_type if file_record else "unknown",
            file_size=file_record.size_bytes if file_record else 0,
            has_extracted_text=has_text
        ))

    return CompanyDocumentListResponse(documents=response_docs)


@router.delete("/companies/{company_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company_document(
    company_id: int,
    document_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Delete a company document.
    Note: File record and storage remain (may be used by other documents).
    """
    # Verify company exists and user owns it
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.user_email == current_user.email
    ).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    # Find document
    document = db.query(CompanyDocument).filter(
        CompanyDocument.id == document_id,
        CompanyDocument.company_id == company_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    try:
        db.delete(document)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        ) from e