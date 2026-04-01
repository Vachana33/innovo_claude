"""
File storage utility — hash-based deduplication + Supabase Storage integration.

Public API:
  compute_file_hash(file_bytes)           -> str
  get_supabase_client()                   -> Client | None
  upload_to_supabase_storage(...)         -> str          (raises on failure)
  get_or_create_file(db, ...)             -> (File, bool)
  get_file_by_id(db, file_id)             -> File | None
  download_from_supabase_storage(path)    -> bytes | None
"""
import hashlib
import logging
import uuid
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import File

try:
    from storage3.exceptions import StorageApiError
except ImportError:
    StorageApiError = Exception  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

# MIME types by file-type key
_CONTENT_TYPE_MAP: dict[str, str] = {
    "audio": "audio/mpeg",
    "pdf":   "application/pdf",
    "docx":  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc":   "application/msword",
}

# Storage extension by file-type key
_EXT_MAP: dict[str, str] = {
    "audio": "m4a",
    "pdf":   "pdf",
    "docx":  "docx",
    "doc":   "doc",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_payload_too_large(err: Exception) -> bool:
    msg = str(err)
    return "413" in msg or "Payload too large" in msg or "exceeded the maximum allowed size" in msg


def _storage_path(file_type: str, content_hash: str) -> str:
    """Build the deterministic storage path for a file."""
    ext = _EXT_MAP.get(file_type, "bin")
    return f"{file_type}/{content_hash[:2]}/{content_hash}.{ext}"


def _attempt_upload(supabase, bucket: str, path: str, file_bytes: bytes,
                    content_type: str) -> None:
    """
    Try uploading with content-type, fall back to no options if the SDK
    rejects the file_options format (older SDK versions).

    Raises StorageApiError or Exception on all other failures.
    Re-raises StorageApiError directly so 413 detection propagates cleanly.
    """
    try:
        supabase.storage.from_(bucket).upload(
            path=path,
            file=file_bytes,
            file_options={"content-type": content_type},
        )
        return
    except StorageApiError:
        raise   # caller handles 413 and other storage errors
    except Exception as primary_err:
        err_str = str(primary_err).lower()
        if "bool" not in err_str and "encode" not in err_str:
            logger.error("file_storage | upload error path=%s error=%s", path, primary_err, exc_info=True)
            raise

    # Fallback: upload without file_options (SDK format mismatch)
    logger.warning("file_storage | retrying upload without file_options path=%s", path)
    supabase.storage.from_(bucket).upload(path=path, file=file_bytes)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_file_hash(file_bytes: bytes) -> str:
    """Return the SHA-256 hex digest of file_bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def get_supabase_client():
    """
    Return an authenticated Supabase client or None if Supabase is not
    configured.

    Uses the service-role key, which bypasses RLS — for backend use only.
    Settings are read from the cached get_settings() singleton so env vars
    are always resolved after load_dotenv() has run in main.py.
    """
    try:
        settings = get_settings()
    except Exception as e:
        logger.warning("file_storage | settings unavailable: %s", e)
        return None

    try:
        from supabase import create_client, Client
        
        # 👇 ADD THIS
        print("DEBUG SUPABASE_URL:", settings.SUPABASE_URL)
        print("DEBUG SUPABASE_KEY (first 10 chars):", settings.SUPABASE_KEY[:10] if settings.SUPABASE_KEY else None)

        client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        return client
    except ImportError:
        logger.error("file_storage | supabase package not installed")
        return None
    except Exception as e:
        logger.error("file_storage | failed to create Supabase client: %s", e)
        return None


def upload_to_supabase_storage(
    file_bytes: bytes,
    file_type: str,
    content_hash: str,
) -> str:
    """
    Upload file_bytes to Supabase Storage and return the storage path.

    Storage path format: {file_type}/{hash_prefix}/{hash}.{ext}
    Files are content-addressed — uploading the same bytes twice is a no-op.

    Raises:
        RuntimeError:  if the Supabase client cannot be initialised.
        StorageApiError: re-raised for 413 Payload Too Large so the caller
                         can convert it to an HTTPException(413).
        Exception:     for all other unrecoverable upload failures.
    """
    supabase = get_supabase_client()
    if not supabase:
        raise RuntimeError(
            "Supabase client unavailable — check SUPABASE_URL and SUPABASE_KEY"
        )

    settings = get_settings()
    bucket = settings.SUPABASE_STORAGE_BUCKET
    path = _storage_path(file_type, content_hash)
    content_type = _CONTENT_TYPE_MAP.get(file_type, "application/octet-stream")

    # Verify bucket exists before attempting upload
    try:
        available = {b.name for b in (supabase.storage.list_buckets() or [])}
        if bucket not in available:
            raise RuntimeError(
                f"Storage bucket '{bucket}' not found. Available: {sorted(available)}"
            )
    except RuntimeError:
        raise
    except Exception as e:
        # Bucket listing failed (permissions, network) — proceed and let the
        # upload itself surface the real error
        logger.warning("file_storage | bucket check failed: %s — proceeding with upload", e)

    try:
        _attempt_upload(supabase, bucket, path, file_bytes, content_type)
    except StorageApiError as e:
        if _is_payload_too_large(e):
            raise   # caller converts to HTTPException(413)
        err_str = str(e).lower()
        if "already exists" in err_str or "duplicate" in err_str or "conflict" in err_str:
            logger.info("file_storage | file already exists path=%s", path)
            return path
        logger.error("file_storage | storage API error path=%s error=%s", path, e, exc_info=True)
        raise
    except Exception as e:
        if _is_payload_too_large(e):
            raise
        err_str = str(e).lower()
        if "already exists" in err_str or "duplicate" in err_str or "conflict" in err_str:
            logger.info("file_storage | file already exists path=%s", path)
            return path
        logger.error("file_storage | upload failed path=%s error=%s", path, e, exc_info=True)
        raise

    logger.info("file_storage | uploaded path=%s file_type=%s size_bytes=%d",
                path, file_type, len(file_bytes))
    return path


def get_or_create_file(
    db: Session,
    file_bytes: bytes,
    file_type: str,
    filename: Optional[str] = None,
) -> Tuple[File, bool]:
    """
    Return an existing File record (by content hash) or create a new one.

    Returns:
        (File, is_new) — is_new=True if the file was just uploaded.

    Raises:
        HTTPException(413): file exceeds Supabase Storage size limit.
        Exception:          for all other upload / DB failures.
    """
    content_hash = compute_file_hash(file_bytes)

    existing = db.query(File).filter(File.content_hash == content_hash).first()
    if existing:
        logger.info("file_storage | dedup hit file_id=%s hash=%s", existing.id, content_hash[:16])
        return existing, False

    try:
        storage_path = upload_to_supabase_storage(file_bytes, file_type, content_hash)
    except StorageApiError as e:
        if _is_payload_too_large(e):
            from fastapi import HTTPException, status as http_status
            size_mb = len(file_bytes) / (1024 * 1024)
            raise HTTPException(
                status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large: {size_mb:.1f} MB (max 50 MB)",
            ) from e
        raise
    except Exception as e:
        if _is_payload_too_large(e):
            from fastapi import HTTPException, status as http_status
            size_mb = len(file_bytes) / (1024 * 1024)
            raise HTTPException(
                status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large: {size_mb:.1f} MB (max 50 MB)",
            ) from e
        raise

    new_file = File(
        id=uuid.uuid4(),
        content_hash=content_hash,
        file_type=file_type,
        storage_path=storage_path,
        size_bytes=len(file_bytes),
    )
    db.add(new_file)
    db.flush()

    logger.info("file_storage | created file_id=%s hash=%s", new_file.id, content_hash[:16])
    return new_file, True


def get_file_by_id(db: Session, file_id: str) -> Optional[File]:
    """Return the File record for file_id, or None if not found / invalid UUID."""
    try:
        fid = uuid.UUID(file_id) if isinstance(file_id, str) else file_id
    except (ValueError, AttributeError):
        return None
    return db.query(File).filter(File.id == fid).first()


def download_from_supabase_storage(storage_path: str) -> Optional[bytes]:
    """
    Download a file from Supabase Storage.

    Returns file bytes, or None if the client is unavailable or the download fails.
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("file_storage | download skipped — client unavailable path=%s", storage_path)
        return None

    bucket = get_settings().SUPABASE_STORAGE_BUCKET
    try:
        data = supabase.storage.from_(bucket).download(storage_path)
        if data:
            return data
        logger.error("file_storage | download returned empty response path=%s", storage_path)
        return None
    except Exception as e:
        logger.error("file_storage | download failed path=%s error=%s", storage_path, e)
        return None
