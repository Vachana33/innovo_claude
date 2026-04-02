from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from innovo_backend.shared.database import get_db
from innovo_backend.shared.models import FundingProgram, Company, Document, funding_program_companies, User, CompanyDocument
from innovo_backend.shared.models import File as FileModel
from innovo_backend.shared.schemas import CompanyCreate, CompanyResponse, CompanyDocumentResponse, CompanyDocumentListResponse
from innovo_backend.shared.extraction import extract_company_profile
from innovo_backend.shared.dependencies import get_current_user, require_admin
from innovo_backend.shared.file_storage import get_or_create_file, get_file_by_id, download_from_supabase_storage, compute_file_hash
from innovo_backend.shared.document_extraction import extract_document_text
from innovo_backend.shared.processing_cache import get_cached_document_text
from innovo_backend.shared.funding_program_documents import get_file_type_from_filename
from typing import List
from datetime import datetime, timezone
import logging
import os
import posthog
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR_ENV = os.getenv("UPLOAD_DIR")
if UPLOAD_DIR_ENV:
    UPLOAD_DIR = Path(UPLOAD_DIR_ENV) / "audio"
else:
    UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent.parent / "uploads" / "audio"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload-audio")
async def upload_audio_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    try:
        from innovo_backend.shared.audio_compression import compress_audio, validate_audio_size  # noqa: PLC0415

        if not file.content_type or not file.content_type.startswith("audio/"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an audio file")

        original_content = await file.read()

        is_valid, error_message = validate_audio_size(original_content)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=error_message)

        original_hash = compute_file_hash(original_content)
        existing_file = db.query(FileModel).filter(FileModel.content_hash == original_hash).first()

        if existing_file:
            return {"file_id": existing_file.id, "audio_path": existing_file.id, "filename": file.filename, "is_new": False}

        input_format = "m4a"
        if file.filename:
            ext = Path(file.filename).suffix.lower().lstrip(".")
            if ext in ["mp3", "wav", "m4a", "aac", "ogg", "flac"]:
                input_format = ext

        compressed_content = compress_audio(original_content, input_format=input_format)

        if not compressed_content:
            logger.warning("Audio compression failed, using original file")
            compressed_content = original_content
        else:
            is_valid_compressed, error_msg = validate_audio_size(compressed_content)
            if not is_valid_compressed:
                logger.warning("Compressed file still too large: %s, using original", error_msg)
                compressed_content = original_content

        compressed_hash = compute_file_hash(compressed_content)
        existing_compressed_file = db.query(FileModel).filter(FileModel.content_hash == compressed_hash).first()

        if existing_compressed_file:
            return {"file_id": existing_compressed_file.id, "audio_path": existing_compressed_file.id, "filename": file.filename, "is_new": False}

        file_record, is_new = get_or_create_file(db=db, file_bytes=compressed_content, file_type="audio", filename=file.filename)
        db.commit()

        return {"file_id": file_record.id, "audio_path": file_record.id, "filename": file.filename, "is_new": is_new}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Error uploading audio file: %s", str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to upload audio file: {str(e)}") from e


def process_company_background(company_id: int, website: str = None, audio_path: str = None):
    from innovo_backend.shared.database import SessionLocal  # noqa: PLC0415

    db = None
    try:
        db = SessionLocal()
        logger.info("Starting preprocessing for company_id=%s", company_id)

        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            logger.error("Company not found for preprocessing: company_id=%s", company_id)
            return

        company.processing_status = "processing"
        company.processing_error = None
        db.commit()

        if website:
            try:
                from innovo_backend.shared.website_scraping import scrape_about_page  # noqa: PLC0415
                from innovo_backend.shared.text_cleaning import clean_website_text  # noqa: PLC0415

                website_raw, _ = scrape_about_page(website, db=db)
                if website_raw:
                    company.website_raw_text = website_raw
                    website_clean = clean_website_text(website_raw)
                    company.website_clean_text = website_clean
                    company.website_text = website_clean
                else:
                    logger.warning("Website data extraction returned no text for company_id=%s", company_id)
            except Exception as e:
                error_msg = f"Website crawl failed: {str(e)}"
                logger.error("Website data extraction failed for company_id=%s: %s", company_id, error_msg)
                company.processing_error = error_msg

        if audio_path:
            try:
                from innovo_backend.shared.text_cleaning import clean_transcript  # noqa: PLC0415

                is_file_id = len(audio_path) == 36 and audio_path.count("-") == 4

                if is_file_id:
                    file_record = get_file_by_id(db, audio_path)
                    if not file_record:
                        raise Exception(f"File not found: file_id={audio_path}")

                    file_bytes = download_from_supabase_storage(file_record.storage_path)
                    if not file_bytes:
                        raise Exception(f"Failed to download file from Supabase Storage: {file_record.storage_path}")

                    import tempfile  # noqa: PLC0415

                    with tempfile.NamedTemporaryFile(delete=False, suffix=".m4a") as tmp_file:
                        tmp_file.write(file_bytes)
                        tmp_audio_path = tmp_file.name

                    try:
                        from innovo_backend.shared.preprocessing import transcribe_audio  # noqa: PLC0415

                        transcript_raw = transcribe_audio(tmp_audio_path, file_content_hash=file_record.content_hash, db=db)
                        if transcript_raw:
                            company.transcript_raw = transcript_raw
                            transcript_clean = clean_transcript(transcript_raw)
                            company.transcript_clean = transcript_clean
                            company.transcript_text = transcript_clean
                    finally:
                        if os.path.exists(tmp_audio_path):
                            os.unlink(tmp_audio_path)
                else:
                    if os.path.isabs(audio_path):
                        resolved_audio_path = audio_path
                    else:
                        resolved_audio_path = str(UPLOAD_DIR / audio_path)

                    from innovo_backend.shared.preprocessing import transcribe_audio  # noqa: PLC0415

                    transcript_raw = transcribe_audio(resolved_audio_path, file_content_hash=None, db=db)
                    if transcript_raw:
                        company.transcript_raw = transcript_raw
                        transcript_clean = clean_transcript(transcript_raw)
                        company.transcript_clean = transcript_clean
                        company.transcript_text = transcript_clean

            except Exception as e:
                error_msg = f"Audio transcription failed: {str(e)}"
                logger.error("Audio transcription failed for company_id=%s: %s", company_id, error_msg)
                if company.processing_error:
                    company.processing_error += f"; {error_msg}"
                else:
                    company.processing_error = error_msg

        company.processing_status = "done"
        company.updated_at = datetime.now(timezone.utc)
        db.commit()

        has_text_data = (company.website_text and company.website_text.strip()) or (
            company.transcript_text and company.transcript_text.strip()
        )
        already_extracted = company.extraction_status == "extracted"

        if has_text_data and not already_extracted:
            try:
                company.extraction_status = "pending"
                db.commit()

                company_profile = extract_company_profile(company.website_text or "", company.transcript_text or "")
                company.company_profile = company_profile
                company.extraction_status = "extracted"
                company.extracted_at = datetime.now(timezone.utc)
                db.commit()
            except Exception as e:
                logger.error("Profile extraction failed for company_id=%s: %s", company_id, str(e))
                try:
                    company.extraction_status = "failed"
                    db.commit()
                except Exception as commit_error:
                    logger.error("Failed to update extraction error status: %s", str(commit_error))

    except Exception as e:
        logger.error("Preprocessing failed for company_id=%s: %s", company_id, str(e))
        if db is not None:
            try:
                company = db.query(Company).filter(Company.id == company_id).first()
                if company:
                    company.processing_status = "failed"
                    company.processing_error = f"Background processing error: {str(e)}"
                    db.commit()
            except Exception as commit_error:
                logger.error("Failed to update error status: %s", str(commit_error))
    finally:
        if db is not None:
            try:
                db.close()
            except Exception as close_error:
                logger.error("Failed to close database session: %s", str(close_error))


@router.post("/funding-programs/{funding_program_id}/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company_in_program(
    funding_program_id: int,
    company_data: CompanyCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email,
    ).first()
    if not funding_program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funding program not found")

    if not company_data.name or not company_data.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company name is required")

    new_company = Company(
        name=company_data.name.strip(),
        website=company_data.website.strip() if company_data.website else None,
        audio_path=company_data.audio_path.strip() if company_data.audio_path else None,
        processing_status="pending",
        user_email=current_user.email,
    )

    try:
        db.add(new_company)
        db.flush()
        db.refresh(funding_program)

        company_already_linked = new_company in funding_program.companies
        if not company_already_linked:
            existing_link = db.execute(
                select(funding_program_companies).where(
                    funding_program_companies.c.funding_program_id == funding_program_id,
                    funding_program_companies.c.company_id == new_company.id,
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
                    "funding_program_id": funding_program_id,
                    "has_website": bool(new_company.website),
                    "has_audio": bool(new_company.audio_path),
                },
            )
        except Exception as e:
            logger.debug("PostHog capture skipped: %s", e)

        if new_company.website or new_company.audio_path:
            background_tasks.add_task(
                process_company_background,
                company_id=new_company.id,
                website=new_company.website,
                audio_path=new_company.audio_path,
            )

        return new_company
    except IntegrityError as e:
        db.rollback()
        error_str = str(e.orig) if hasattr(e, "orig") else str(e)
        if "funding_program_companies" in error_str and "UNIQUE" in error_str:
            existing_company = db.query(Company).filter(
                Company.name == company_data.name.strip(),
                Company.user_email == current_user.email,
            ).first()
            if existing_company:
                db.refresh(funding_program)
                if existing_company not in funding_program.companies:
                    funding_program.companies.append(existing_company)
                    db.commit()
                return existing_company
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create company: {str(e)}") from e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create company: {str(e)}") from e


@router.get("/funding-programs/{funding_program_id}/companies", response_model=List[CompanyResponse])
def get_companies_for_program(
    funding_program_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email,
    ).first()
    if not funding_program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funding program not found")

    return [c for c in funding_program.companies if c.user_email == current_user.email]


@router.post("/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    company_data: CompanyCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    require_admin(current_user)
    if not company_data.name or not company_data.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company name is required")

    new_company = Company(
        name=company_data.name.strip(),
        website=company_data.website.strip() if company_data.website else None,
        audio_path=company_data.audio_path.strip() if company_data.audio_path else None,
        processing_status="pending",
        user_email=current_user.email,
    )

    try:
        db.add(new_company)
        db.commit()
        db.refresh(new_company)

        try:
            posthog.capture(
                "company_created",
                distinct_id=current_user.email,
                properties={"company_id": new_company.id, "has_website": bool(new_company.website), "has_audio": bool(new_company.audio_path)},
            )
        except Exception as e:
            logger.debug("PostHog capture skipped: %s", e)

        if new_company.website or new_company.audio_path:
            background_tasks.add_task(
                process_company_background,
                company_id=new_company.id,
                website=new_company.website,
                audio_path=new_company.audio_path,
            )

        return new_company
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create company: {str(e)}") from e


@router.get("/companies", response_model=List[CompanyResponse])
def get_all_companies(
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    return db.query(Company).filter(Company.user_email == current_user.email).order_by(Company.created_at.desc()).all()


@router.get("/companies/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    company = db.query(Company).filter(Company.id == company_id, Company.user_email == current_user.email).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.post("/funding-programs/{funding_program_id}/companies/{company_id}", response_model=CompanyResponse)
def import_company_to_program(
    funding_program_id: int,
    company_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    funding_program = db.query(FundingProgram).filter(
        FundingProgram.id == funding_program_id,
        FundingProgram.user_email == current_user.email,
    ).first()
    if not funding_program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funding program not found")

    company = db.query(Company).filter(Company.id == company_id, Company.user_email == current_user.email).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if company in funding_program.companies:
        return company

    try:
        funding_program.companies.append(company)
        db.commit()
        db.refresh(company)
        return company
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to import company: {str(e)}") from e


@router.put("/companies/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    company_data: CompanyCreate,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    require_admin(current_user)
    company = db.query(Company).filter(Company.id == company_id, Company.user_email == current_user.email).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if not company_data.name or not company_data.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company name is required")

    company.name = company_data.name.strip()
    company.website = company_data.website.strip() if company_data.website else None
    company.audio_path = company_data.audio_path.strip() if company_data.audio_path else None

    try:
        db.commit()
        db.refresh(company)
        return company
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update company") from e


@router.delete("/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    require_admin(current_user)
    company = db.query(Company).filter(Company.id == company_id, Company.user_email == current_user.email).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    try:
        db.query(Document).filter(Document.company_id == company_id).delete()
        db.execute(delete(funding_program_companies).where(funding_program_companies.c.company_id == company_id))
        db.delete(company)
        db.commit()
        try:
            posthog.capture("company_deleted", distinct_id=current_user.email, properties={"company_id": company_id})
        except Exception as e:
            logger.debug("PostHog capture skipped: %s", e)
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete company") from e


@router.post("/companies/{company_id}/documents/upload", response_model=List[CompanyDocumentResponse])
async def upload_company_documents(
    company_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    require_admin(current_user)
    company = db.query(Company).filter(Company.id == company_id, Company.user_email == current_user.email).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    uploaded_documents = []

    try:
        for file in files:
            content = await file.read()
            file_type = get_file_type_from_filename(file.filename or "unknown")

            if file_type not in ["pdf", "docx"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported file type: {file_type}. Only PDF and DOCX files are allowed.")

            file_record, _ = get_or_create_file(db=db, file_bytes=content, file_type=file_type, filename=file.filename)
            extract_document_text(file_bytes=content, file_content_hash=file_record.content_hash, file_type=file_type, db=db)

            company_document = CompanyDocument(
                company_id=company_id,
                file_id=file_record.id,
                original_filename=file.filename or "unknown",
                uploaded_by=current_user.email,
            )
            db.add(company_document)
            uploaded_documents.append(company_document)

        db.commit()

        for doc in uploaded_documents:
            db.refresh(doc)

        response_docs = []
        for doc in uploaded_documents:
            fr = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
            has_text = False
            if fr:
                if fr.file_type in ["pdf", "docx"]:
                    has_text = get_cached_document_text(db, fr.content_hash) is not None
                elif fr.file_type == "txt":
                    has_text = True

            response_docs.append(CompanyDocumentResponse(
                id=str(doc.id),
                company_id=doc.company_id,
                file_id=str(doc.file_id),
                original_filename=doc.original_filename,
                display_name=doc.display_name,
                uploaded_at=doc.uploaded_at,
                file_type=fr.file_type if fr else "unknown",
                file_size=fr.size_bytes if fr else 0,
                has_extracted_text=has_text,
            ))

        return response_docs

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to upload documents: {str(e)}") from e


@router.get("/companies/{company_id}/documents", response_model=CompanyDocumentListResponse)
def get_company_documents(
    company_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    company = db.query(Company).filter(Company.id == company_id, Company.user_email == current_user.email).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    documents = db.query(CompanyDocument).filter(CompanyDocument.company_id == company_id).all()

    response_docs = []
    for doc in documents:
        fr = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
        has_text = False
        if fr:
            if fr.file_type in ["pdf", "docx"]:
                has_text = get_cached_document_text(db, fr.content_hash) is not None
            elif fr.file_type == "txt":
                has_text = True

        response_docs.append(CompanyDocumentResponse(
            id=str(doc.id),
            company_id=doc.company_id,
            file_id=str(doc.file_id),
            original_filename=doc.original_filename,
            display_name=doc.display_name,
            uploaded_at=doc.uploaded_at,
            file_type=fr.file_type if fr else "unknown",
            file_size=fr.size_bytes if fr else 0,
            has_extracted_text=has_text,
        ))

    return CompanyDocumentListResponse(documents=response_docs)


@router.delete("/companies/{company_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company_document(
    company_id: int,
    document_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    company = db.query(Company).filter(Company.id == company_id, Company.user_email == current_user.email).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    document = db.query(CompanyDocument).filter(
        CompanyDocument.id == document_id,
        CompanyDocument.company_id == company_id,
    ).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    try:
        db.delete(document)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete document: {str(e)}") from e
