"""
Phase 2: Raw Processing Cache Utilities

Provides caching for raw processing outputs (audio transcripts, website text, document text)
to ensure each input is processed exactly once and reused everywhere.
"""
import hashlib
import logging
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.models import AudioTranscriptCache, WebsiteTextCache, DocumentTextCache
import uuid

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """
    Normalize a URL for consistent hashing.

    Normalization rules:
    - Ensure scheme (http/https)
    - Remove trailing slashes
    - Convert to lowercase
    - Remove default ports (80, 443)
    - Remove www. prefix (optional - can be kept if needed)

    Args:
        url: Raw URL string

    Returns:
        Normalized URL string
    """
    if not url:
        return ""

    # Ensure URL has a scheme
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url.lower().rstrip('/'))

    # Remove default ports
    netloc = parsed.netloc
    if netloc.endswith(':80') and parsed.scheme == 'http':
        netloc = netloc[:-3]
    elif netloc.endswith(':443') and parsed.scheme == 'https':
        netloc = netloc[:-4]

    # Reconstruct normalized URL
    normalized = urlunparse((
        parsed.scheme,
        netloc,
        parsed.path,
        parsed.params,
        parsed.query,  # Keep query string for now (can be removed if needed)
        parsed.fragment  # Remove fragment
    ))

    return normalized


def hash_url(url: str) -> str:
    """
    Compute SHA256 hash of normalized URL.

    Args:
        url: URL string (will be normalized)

    Returns:
        SHA256 hash as hexadecimal string
    """
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def get_cached_audio_transcript(db: Session, file_content_hash: str) -> Optional[str]:
    """
    Get cached audio transcript by file content_hash.

    Args:
        db: Database session
        file_content_hash: SHA256 hash of file content

    Returns:
        Cached transcript text or None if not found
    """
    cache_entry = db.query(AudioTranscriptCache).filter(
        AudioTranscriptCache.file_content_hash == file_content_hash
    ).first()

    if cache_entry:
        logger.info(f"[CACHE HIT] Audio transcript found for content_hash={file_content_hash[:16]}... (processed_at={cache_entry.processed_at})")
        return cache_entry.transcript_text
    else:
        logger.info(f"[CACHE MISS] No cached audio transcript for content_hash={file_content_hash[:16]}...")
        return None


def store_audio_transcript(db: Session, file_content_hash: str, transcript_text: str) -> None:
    """
    Store audio transcript in cache.

    Args:
        db: Database session
        file_content_hash: SHA256 hash of file content
        transcript_text: Transcript text from Whisper
    """
    try:
        cache_entry = AudioTranscriptCache(
            id=uuid.uuid4(),
            file_content_hash=file_content_hash,
            transcript_text=transcript_text,
            processed_at=datetime.now(timezone.utc)
        )
        db.add(cache_entry)
        db.commit()
        logger.info(f"[CACHE STORE] Stored audio transcript for content_hash={file_content_hash[:16]}... (length={len(transcript_text)} chars)")
    except Exception as e:
        db.rollback()
        logger.error(f"[CACHE ERROR] Failed to store audio transcript: {str(e)}")
        raise


def get_cached_website_text(db: Session, url: str) -> Optional[str]:
    """
    Get cached website text by normalized URL hash.

    Args:
        db: Database session
        url: Website URL (will be normalized and hashed)

    Returns:
        Cached website text or None if not found
    """
    url_hash = hash_url(url)
    normalized_url = normalize_url(url)

    cache_entry = db.query(WebsiteTextCache).filter(
        WebsiteTextCache.url_hash == url_hash
    ).first()

    if cache_entry:
        logger.info(f"[CACHE HIT] Website text found for url={normalized_url} (processed_at={cache_entry.processed_at})")
        return cache_entry.website_text
    else:
        logger.info(f"[CACHE MISS] No cached website text for url={normalized_url}")
        return None


def store_website_text(db: Session, url: str, website_text: str) -> None:
    """
    Store website text in cache.

    Args:
        db: Database session
        url: Website URL (will be normalized and hashed)
        website_text: Crawled website text
    """
    try:
        url_hash = hash_url(url)
        normalized_url = normalize_url(url)

        cache_entry = WebsiteTextCache(
            id=uuid.uuid4(),
            url_hash=url_hash,
            normalized_url=normalized_url,
            website_text=website_text,
            processed_at=datetime.now(timezone.utc)
        )
        db.add(cache_entry)
        db.commit()
        logger.info(f"[CACHE STORE] Stored website text for url={normalized_url} (length={len(website_text)} chars)")
    except Exception as e:
        db.rollback()
        logger.error(f"[CACHE ERROR] Failed to store website text: {str(e)}")
        raise


def get_cached_document_text(db: Session, file_content_hash: str) -> Optional[str]:
    """
    Get cached document text by file content_hash.

    Args:
        db: Database session
        file_content_hash: SHA256 hash of file content

    Returns:
        Cached extracted text or None if not found
    """
    cache_entry = db.query(DocumentTextCache).filter(
        DocumentTextCache.file_content_hash == file_content_hash
    ).first()

    if cache_entry:
        logger.info(f"[CACHE HIT] Document text found for content_hash={file_content_hash[:16]}... (processed_at={cache_entry.processed_at})")
        return cache_entry.extracted_text
    else:
        logger.info(f"[CACHE MISS] No cached document text for content_hash={file_content_hash[:16]}...")
        return None


def store_document_text(db: Session, file_content_hash: str, extracted_text: str) -> None:
    """
    Store document text in cache.

    Args:
        db: Database session
        file_content_hash: SHA256 hash of file content
        extracted_text: Extracted text from PDF/DOCX
    """
    try:
        cache_entry = DocumentTextCache(
            id=uuid.uuid4(),
            file_content_hash=file_content_hash,
            extracted_text=extracted_text,
            processed_at=datetime.now(timezone.utc)
        )
        db.add(cache_entry)
        db.commit()
        logger.info(f"[CACHE STORE] Stored document text for content_hash={file_content_hash[:16]}... (length={len(extracted_text)} chars)")
    except Exception as e:
        db.rollback()
        logger.error(f"[CACHE ERROR] Failed to store document text: {str(e)}")
        raise
