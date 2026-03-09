"""
File storage utility for hash-based deduplication and Supabase Storage integration.
Phase 1: Infrastructure & Deduplication
"""
import hashlib
import os
import logging
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models import File
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Import StorageApiError for proper error handling
try:
    from storage3.exceptions import StorageApiError
except ImportError:
    # Fallback if storage3 is not available
    StorageApiError = Exception

# Load .env file if it exists (fallback in case main.py hasn't loaded it yet)
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)

logger = logging.getLogger(__name__)

# Supabase configuration from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "files")

def compute_file_hash(file_bytes: bytes) -> str:
    """
    Compute SHA256 hash of file bytes.

    Args:
        file_bytes: The file content as bytes

    Returns:
        SHA256 hash as hexadecimal string
    """
    return hashlib.sha256(file_bytes).hexdigest()


def get_supabase_client():
    """
    Get Supabase client instance using service_role key.

    Note: Backend uses service_role key which bypasses RLS policies.
    This allows full access to private storage buckets without requiring
    storage policies.

    Returns:
        Supabase client or None if not configured
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase not configured (SUPABASE_URL or SUPABASE_KEY not set)")
        return None

    try:
        from supabase import create_client, Client
        # Uses service_role key from environment (bypasses RLS)
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return supabase
    except ImportError:
        logger.error("supabase library not installed. Run: pip install supabase")
        return None
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {str(e)}")
        return None


def upload_to_supabase_storage(file_bytes: bytes, file_type: str, content_hash: str) -> Optional[str]:
    """
    Upload file to Supabase Storage.

    Args:
        file_bytes: The file content as bytes
        file_type: File type (e.g., "audio", "pdf", "docx")
        content_hash: SHA256 hash of the file (used for path)

    Returns:
        Storage path in Supabase Storage, or None if upload fails
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Cannot upload to Supabase Storage: Supabase client not available. Check SUPABASE_URL and SUPABASE_KEY environment variables.")
        return None

    try:
        # Create storage path using hash (first 2 chars for directory structure)
        # Format: {file_type}/{hash_prefix}/{hash}.{ext}
        hash_prefix = content_hash[:2]
        # Determine file extension from file_type
        ext_map = {
            "audio": "m4a",  # Default for audio files
            "pdf": "pdf",
            "docx": "docx",
            "doc": "doc",
        }
        ext = ext_map.get(file_type, "bin")
        storage_path = f"{file_type}/{hash_prefix}/{content_hash}.{ext}"

        try:
            # Check if bucket exists and is accessible
            try:
                buckets = supabase.storage.list_buckets()
                bucket_names = [b.name for b in buckets] if buckets else []
                if SUPABASE_STORAGE_BUCKET not in bucket_names:
                    logger.error(f"Supabase Storage bucket '{SUPABASE_STORAGE_BUCKET}' does not exist. Available buckets: {bucket_names}")
                    return None
            except Exception as bucket_check_error:
                logger.warning(f"Could not verify bucket existence: {str(bucket_check_error)}")

            # Upload file - use correct content-type for audio
            content_type_map = {
                "audio": "audio/mpeg",
                "pdf": "application/pdf",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "doc": "application/msword",
            }
            content_type = content_type_map.get(file_type, "application/octet-stream")

            # Supabase 2.27+ API: Pass raw bytes directly, not BytesIO
            # The newer SDK expects bytes or file path, not BytesIO objects
            # file_options only accepts string values (content-type), not booleans
            # Note: upsert behavior is handled automatically by the SDK
            try:
                response = supabase.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                    path=storage_path,
                    file=file_bytes,  # Pass raw bytes directly
                    file_options={"content-type": content_type}
                )
            except StorageApiError as storage_error:
                # Handle Supabase Storage API errors (including 413 Payload Too Large)
                error_str = str(storage_error)
                # Check if it's a 413 error (Payload Too Large)
                if "413" in error_str or "Payload too large" in error_str or "exceeded the maximum allowed size" in error_str:
                    # Re-raise as-is so it can be caught and converted to HTTPException(413)
                    raise
                # Other StorageApiError (permissions, etc.)
                logger.error(f"Supabase Storage API error: {str(storage_error)}", exc_info=True)
                raise
            except Exception as upload_error:
                # If upload with content-type fails, try without file_options
                error_str = str(upload_error)
                if "bool" in error_str.lower() or "encode" in error_str.lower():
                    logger.warning(f"Upload with file_options failed (format issue): {str(upload_error)}, trying without options")
                    try:
                        response = supabase.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                            path=storage_path,
                            file=file_bytes  # Pass raw bytes directly
                        )
                    except StorageApiError as fallback_storage_error:
                        # Check if fallback also has 413 error
                        fallback_str = str(fallback_storage_error)
                        if "413" in fallback_str or "Payload too large" in fallback_str or "exceeded the maximum allowed size" in fallback_str:
                            raise
                        logger.error(f"Supabase Storage API error: {str(fallback_storage_error)}", exc_info=True)
                        raise
                    except Exception as fallback_error:
                        logger.error(f"Upload failed even without options: {str(fallback_error)}", exc_info=True)
                        raise upload_error
                else:
                    # Other errors (permissions, network, etc.)
                    logger.error(f"Upload error: {str(upload_error)}", exc_info=True)
                    raise

            # Supabase returns a dict with 'path' key on success
            logger.info(f"File uploaded to Supabase Storage: {storage_path}")
            return storage_path
        except Exception as upload_error:
            # If file already exists (upsert), that's okay
            error_str = str(upload_error).lower()
            if "already exists" in error_str or "duplicate" in error_str or "conflict" in error_str:
                logger.info(f"File already exists in Supabase Storage: {storage_path}")
                return storage_path
            else:
                logger.error(f"Error uploading to Supabase Storage: {str(upload_error)}", exc_info=True)
                raise

    except Exception as e:
        logger.error(f"Error uploading to Supabase Storage: {str(e)}", exc_info=True)
        return None


def get_or_create_file(
    db: Session,
    file_bytes: bytes,
    file_type: str,
    filename: Optional[str] = None
) -> Tuple[File, bool]:
    """
    Get existing file by hash or create new file record.
    Implements hash-based deduplication.

    Args:
        db: Database session
        file_bytes: The file content as bytes
        file_type: File type (e.g., "audio", "pdf", "docx")
        filename: Original filename (optional)

    Returns:
        Tuple of (File object, is_new: bool)
        - is_new=True if file was just created
        - is_new=False if existing file was reused
    
    Raises:
        HTTPException(413): If file is too large for Supabase Storage
        Exception: For other upload failures
    """
    # Compute hash
    content_hash = compute_file_hash(file_bytes)
    size_bytes = len(file_bytes)

    # Check if file with this hash already exists
    existing_file = db.query(File).filter(File.content_hash == content_hash).first()

    if existing_file:
        logger.info(f"File with hash {content_hash} already exists (file_id={existing_file.id}), reusing")
        return existing_file, False

    # File doesn't exist, create new record
    # Upload to Supabase Storage
    try:
        storage_path = upload_to_supabase_storage(file_bytes, file_type, content_hash)
    except StorageApiError as storage_error:
        # Handle Supabase Storage API errors (including 413 Payload Too Large)
        error_str = str(storage_error)
        if "413" in error_str or "Payload too large" in error_str or "exceeded the maximum allowed size" in error_str:
            from fastapi import HTTPException, status
            size_mb = size_bytes / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large for upload: {size_mb:.1f}MB. Maximum allowed size is 50MB."
            ) from storage_error
        # Re-raise other StorageApiError
        raise
    except Exception as upload_error:
        # Check if it's a 413 Payload Too Large error (in case it's wrapped)
        error_str = str(upload_error)
        if "413" in error_str or "Payload too large" in error_str or "exceeded the maximum allowed size" in error_str:
            from fastapi import HTTPException, status
            size_mb = size_bytes / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large for upload: {size_mb:.1f}MB. Maximum allowed size is 50MB."
            ) from upload_error
        # Re-raise other errors
        raise

    if not storage_path:
        error_msg = "Failed to upload file to Supabase Storage"
        if not SUPABASE_URL or not SUPABASE_KEY:
            error_msg += " (SUPABASE_URL or SUPABASE_KEY not configured)"
        raise Exception(error_msg)

    # Create file record
    new_file = File(
        id=uuid.uuid4(),
        content_hash=content_hash,
        file_type=file_type,
        storage_path=storage_path,
        size_bytes=size_bytes
    )

    db.add(new_file)
    db.flush()  # Flush to get the ID

    logger.info(f"Created new file record (file_id={new_file.id}, hash={content_hash})")
    return new_file, True


def get_file_by_id(db: Session, file_id: str) -> Optional[File]:
    """
    Get file record by ID.

    Args:
        db: Database session
        file_id: File UUID as string

    Returns:
        File object or None if not found
    """
    # Convert string to UUID object for proper type matching with UUID(as_uuid=True)
    try:
        file_uuid = uuid.UUID(file_id) if isinstance(file_id, str) else file_id
    except (ValueError, AttributeError):
        # Invalid UUID format
        return None
    return db.query(File).filter(File.id == file_uuid).first()


def download_from_supabase_storage(storage_path: str) -> Optional[bytes]:
    """
    Download file from Supabase Storage.

    Args:
        storage_path: Path in Supabase Storage

    Returns:
        File bytes or None if download fails
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Cannot download from Supabase Storage: Supabase client not available. Check SUPABASE_URL and SUPABASE_KEY environment variables.")
        return None

    try:
        response = supabase.storage.from_(SUPABASE_STORAGE_BUCKET).download(storage_path)
        if response:
            return response
        else:
            logger.error(f"Failed to download file from Supabase Storage: {storage_path}")
            return None
    except Exception as e:
        logger.error(f"Error downloading from Supabase Storage: {str(e)}")
        return None
