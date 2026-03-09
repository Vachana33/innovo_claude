"""
Alte Vorhabensbeschreibung router.
System-level module for historical writing style extraction.
Completely separate from Funding Programs and Companies.
"""
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime, timezone

from app.database import get_db
from app.models import (
    AlteVorhabensbeschreibungDocument,
    AlteVorhabensbeschreibungStyleProfile,
    File as FileModel,
    User
)
from app.dependencies import get_current_user
from app.file_storage import get_or_create_file
from app.document_extraction import extract_document_text
from app.processing_cache import get_cached_document_text
from app.funding_program_documents import get_file_type_from_filename
from app.style_extraction import generate_style_profile, compute_combined_hash
from app.schemas import AlteVorhabensbeschreibungDocumentResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def regenerate_style_profile(db: Session) -> Optional[AlteVorhabensbeschreibungStyleProfile]:
    """
    Regenerate style profile from all uploaded documents (system-level).
    Uses documents from all users to create a shared system-level style profile.
    
    Returns:
        Updated or newly created style profile, or None if no documents exist
    """
    # Get all documents (system-level, from all users)
    documents = db.query(AlteVorhabensbeschreibungDocument).all()
    
    if not documents:
        logger.info("No documents found for style profile generation")
        return None
    
    # Collect content hashes and extract texts
    content_hashes = []
    doc_texts = []
    
    for doc in documents:
        file_record = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
        if not file_record:
            logger.warning(f"File record not found for document {doc.id}")
            continue
        
        content_hashes.append(file_record.content_hash)
        
        # Get extracted text from cache
        text = get_cached_document_text(db, file_record.content_hash)
        if text:
            doc_texts.append(text)
        else:
            logger.warning(f"No extracted text found for file {file_record.id} (hash: {file_record.content_hash})")
    
    if not doc_texts:
        logger.warning("No extracted text available for style profile generation")
        return None
    
    # Compute combined hash
    combined_hash = compute_combined_hash(content_hashes)
    
    # Check if profile exists and hash matches
    existing_profile = db.query(AlteVorhabensbeschreibungStyleProfile).filter(
        AlteVorhabensbeschreibungStyleProfile.combined_hash == combined_hash
    ).first()
    
    if existing_profile:
        logger.info(f"Style profile already exists with matching hash: {combined_hash[:16]}...")
        return existing_profile
    
    # Generate new style profile
    logger.info(f"Generating new style profile from {len(doc_texts)} documents")
    style_summary_json = generate_style_profile(doc_texts)
    
    # Delete old profile if exists (only one active profile)
    old_profiles = db.query(AlteVorhabensbeschreibungStyleProfile).all()
    for old_profile in old_profiles:
        db.delete(old_profile)
    
    # Create new profile
    new_profile = AlteVorhabensbeschreibungStyleProfile(
        combined_hash=combined_hash,
        style_summary_json=style_summary_json,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    
    logger.info(f"Successfully created new style profile with hash: {combined_hash[:16]}...")
    return new_profile


@router.post("/alte-vorhabensbeschreibung/upload", response_model=List[AlteVorhabensbeschreibungDocumentResponse])
async def upload_alte_vorhabensbeschreibung_documents(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Upload multiple PDF documents for historical writing style extraction.
    
    - Accepts: PDF files only
    - Extracts text and stores in DocumentTextCache
    - Creates AlteVorhabensbeschreibungDocument records
    - Triggers style profile regeneration after upload
    """
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
            
            # Validate file type - only PDF allowed
            if file_type != "pdf":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file type: {file_type}. Only PDF files are allowed."
                )
            
            # Get or create file record (hash-based deduplication)
            file_record, is_new = get_or_create_file(
                db=db,
                file_bytes=content,
                file_type=file_type,
                filename=file.filename
            )
            
            # Extract text for PDFs (uses existing caching, ignores images)
            extracted_text = extract_document_text(
                file_bytes=content,
                file_content_hash=file_record.content_hash,
                file_type=file_type,
                db=db
            )
            
            if not extracted_text or not extracted_text.strip():
                logger.warning(f"Extracted text is empty for file {file.filename}, continuing anyway")
            
            # Create AlteVorhabensbeschreibungDocument record
            document = AlteVorhabensbeschreibungDocument(
                file_id=file_record.id,
                original_filename=file.filename or "unknown",
                uploaded_by=current_user.email
            )
            
            db.add(document)
            uploaded_documents.append(document)
            
            logger.info(f"Uploaded Alte Vorhabensbeschreibung document: {file.filename} (file_type: {file_type})")
        
        db.commit()
        
        # Refresh documents to get IDs
        for doc in uploaded_documents:
            db.refresh(doc)
        
        # Trigger style profile regeneration
        try:
            regenerate_style_profile(db)
        except Exception as e:
            logger.error(f"Error regenerating style profile after upload: {str(e)}")
            # Don't fail the upload if regeneration fails
        
        # Build response
        response_docs = []
        for doc in uploaded_documents:
            file_record = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
            response_docs.append(AlteVorhabensbeschreibungDocumentResponse(
                id=str(doc.id),
                file_id=str(doc.file_id),
                original_filename=doc.original_filename,
                uploaded_at=doc.uploaded_at.isoformat(),
                file_type=file_record.file_type if file_record else "unknown",
                file_size=file_record.size_bytes if file_record else 0,
            ))
        
        return response_docs
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading Alte Vorhabensbeschreibung documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload documents: {str(e)}"
        ) from e


@router.get("/alte-vorhabensbeschreibung/documents", response_model=List[AlteVorhabensbeschreibungDocumentResponse])
def get_alte_vorhabensbeschreibung_documents(
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Get all Alte Vorhabensbeschreibung documents uploaded by the current user.
    """
    documents = db.query(AlteVorhabensbeschreibungDocument).filter(
        AlteVorhabensbeschreibungDocument.uploaded_by == current_user.email
    ).order_by(AlteVorhabensbeschreibungDocument.uploaded_at.desc()).all()
    
    response_docs = []
    for doc in documents:
        file_record = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
        response_docs.append(AlteVorhabensbeschreibungDocumentResponse(
            id=str(doc.id),
            file_id=str(doc.file_id),
            original_filename=doc.original_filename,
            uploaded_at=doc.uploaded_at.isoformat(),
            file_type=file_record.file_type if file_record else "unknown",
            file_size=file_record.size_bytes if file_record else 0,
        ))
    
    return response_docs


@router.put("/alte-vorhabensbeschreibung/documents/{document_id}", response_model=AlteVorhabensbeschreibungDocumentResponse)
async def update_alte_vorhabensbeschreibung_document(
    document_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Update/replace an Alte Vorhabensbeschreibung document with a new PDF file.
    Triggers style profile regeneration after update.
    """
    # Find document and verify ownership
    document = db.query(AlteVorhabensbeschreibungDocument).filter(
        AlteVorhabensbeschreibungDocument.id == document_id,
        AlteVorhabensbeschreibungDocument.uploaded_by == current_user.email
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    try:
        # Read file content
        content = await file.read()
        
        # Determine file type
        file_type = get_file_type_from_filename(file.filename or "unknown")
        
        # Validate file type - only PDF allowed
        if file_type != "pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_type}. Only PDF files are allowed."
            )
        
        # Get or create file record (hash-based deduplication)
        file_record, is_new = get_or_create_file(
            db=db,
            file_bytes=content,
            file_type=file_type,
            filename=file.filename
        )
        
        # Extract text for PDFs (uses existing caching, ignores images)
        extracted_text = extract_document_text(
            file_bytes=content,
            file_content_hash=file_record.content_hash,
            file_type=file_type,
            db=db
        )
        
        if not extracted_text or not extracted_text.strip():
            logger.warning(f"Extracted text is empty for file {file.filename}, continuing anyway")
        
        # Update document record
        document.file_id = file_record.id
        document.original_filename = file.filename or "unknown"
        # uploaded_at and uploaded_by remain unchanged
        
        db.commit()
        db.refresh(document)
        
        # Trigger style profile regeneration
        try:
            regenerate_style_profile(db)
        except Exception as e:
            logger.error(f"Error regenerating style profile after update: {str(e)}")
            # Don't fail the update if regeneration fails
        
        # Build response
        file_record_response = db.query(FileModel).filter(FileModel.id == document.file_id).first()
        return AlteVorhabensbeschreibungDocumentResponse(
            id=str(document.id),
            file_id=str(document.file_id),
            original_filename=document.original_filename,
            uploaded_at=document.uploaded_at.isoformat(),
            file_type=file_record_response.file_type if file_record_response else "unknown",
            file_size=file_record_response.size_bytes if file_record_response else 0,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating Alte Vorhabensbeschreibung document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update document: {str(e)}"
        ) from e


@router.delete("/alte-vorhabensbeschreibung/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alte_vorhabensbeschreibung_document(
    document_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Delete an Alte Vorhabensbeschreibung document.
    Note: File record and storage remain (may be used by other documents).
    Triggers style profile regeneration after deletion.
    """
    # Find document and verify ownership
    document = db.query(AlteVorhabensbeschreibungDocument).filter(
        AlteVorhabensbeschreibungDocument.id == document_id,
        AlteVorhabensbeschreibungDocument.uploaded_by == current_user.email
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    try:
        db.delete(document)
        db.commit()
        
        # Trigger style profile regeneration
        try:
            regenerate_style_profile(db)
        except Exception as e:
            logger.error(f"Error regenerating style profile after deletion: {str(e)}")
            # Don't fail the deletion if regeneration fails
        
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        ) from e


@router.get("/alte-vorhabensbeschreibung/style-profile", response_model=dict)
def get_style_profile(
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Get the current style profile and metadata.
    """
    # Get all documents (system-level) to compute hash
    documents = db.query(AlteVorhabensbeschreibungDocument).all()
    
    # Get current user's documents count for display
    user_documents = db.query(AlteVorhabensbeschreibungDocument).filter(
        AlteVorhabensbeschreibungDocument.uploaded_by == current_user.email
    ).all()
    
    content_hashes = []
    for doc in documents:
        file_record = db.query(FileModel).filter(FileModel.id == doc.file_id).first()
        if file_record:
            content_hashes.append(file_record.content_hash)
    
    current_hash = compute_combined_hash(content_hashes) if content_hashes else None
    
    # Get existing profile
    profile = db.query(AlteVorhabensbeschreibungStyleProfile).first()
    
    if not profile:
        return {
            "status": "not_generated",
            "documents_count": len(user_documents),  # User's own documents count
            "total_documents_count": len(documents),  # Total system documents
            "combined_hash": current_hash,
            "style_summary_json": None,
            "created_at": None,
            "updated_at": None
        }
    
    # Check if hash matches
    is_active = profile.combined_hash == current_hash if current_hash else False
    
    return {
        "status": "active" if is_active else "outdated",
        "documents_count": len(user_documents),  # User's own documents count
        "total_documents_count": len(documents),  # Total system documents
        "combined_hash": current_hash,
        "style_summary_json": profile.style_summary_json,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
        "profile_hash": profile.combined_hash
    }


@router.post("/alte-vorhabensbeschreibung/regenerate-style", response_model=dict)
def regenerate_style(
    db: Session = Depends(get_db),  # noqa: B008
    current_user: User = Depends(get_current_user)  # noqa: B008
):
    """
    Manually trigger style profile regeneration.
    """
    try:
        profile = regenerate_style_profile(db)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No documents available for style profile generation"
            )
        
        return {
            "status": "success",
            "message": "Style profile regenerated successfully",
            "combined_hash": profile.combined_hash,
            "created_at": profile.created_at.isoformat(),
            "updated_at": profile.updated_at.isoformat()
        }
    except Exception as e:
        logger.error(f"Error regenerating style profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate style profile: {str(e)}"
        ) from e
