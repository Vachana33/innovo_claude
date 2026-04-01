"""Phase 2: Raw Processing Cache Utilities"""
import hashlib
import logging
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from innovo_backend.shared.models import AudioTranscriptCache, WebsiteTextCache, DocumentTextCache
import uuid

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url.lower().rstrip("/"))
    netloc = parsed.netloc
    if netloc.endswith(":80") and parsed.scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and parsed.scheme == "https":
        netloc = netloc[:-4]
    normalized = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    return normalized


def hash_url(url: str) -> str:
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached_audio_transcript(db: Session, file_content_hash: str) -> Optional[str]:
    cache_entry = db.query(AudioTranscriptCache).filter(
        AudioTranscriptCache.file_content_hash == file_content_hash
    ).first()
    if cache_entry:
        logger.info(f"[CACHE HIT] Audio transcript found for content_hash={file_content_hash[:16]}...")
        return cache_entry.transcript_text
    logger.info(f"[CACHE MISS] No cached audio transcript for content_hash={file_content_hash[:16]}...")
    return None


def store_audio_transcript(db: Session, file_content_hash: str, transcript_text: str) -> None:
    try:
        cache_entry = AudioTranscriptCache(
            id=uuid.uuid4(),
            file_content_hash=file_content_hash,
            transcript_text=transcript_text,
            processed_at=datetime.now(timezone.utc),
        )
        db.add(cache_entry)
        db.commit()
        logger.info(f"[CACHE STORE] Stored audio transcript for content_hash={file_content_hash[:16]}...")
    except Exception as e:
        db.rollback()
        logger.error(f"[CACHE ERROR] Failed to store audio transcript: {str(e)}")
        raise


def get_cached_website_text(db: Session, url: str) -> Optional[str]:
    url_hash = hash_url(url)
    normalized_url = normalize_url(url)
    cache_entry = db.query(WebsiteTextCache).filter(WebsiteTextCache.url_hash == url_hash).first()
    if cache_entry:
        logger.info(f"[CACHE HIT] Website text found for url={normalized_url}")
        return cache_entry.website_text
    logger.info(f"[CACHE MISS] No cached website text for url={normalized_url}")
    return None


def store_website_text(db: Session, url: str, website_text: str) -> None:
    try:
        url_hash = hash_url(url)
        normalized_url = normalize_url(url)
        cache_entry = WebsiteTextCache(
            id=uuid.uuid4(),
            url_hash=url_hash,
            normalized_url=normalized_url,
            website_text=website_text,
            processed_at=datetime.now(timezone.utc),
        )
        db.add(cache_entry)
        db.commit()
        logger.info(f"[CACHE STORE] Stored website text for url={normalized_url}")
    except Exception as e:
        db.rollback()
        logger.error(f"[CACHE ERROR] Failed to store website text: {str(e)}")
        raise


def get_cached_document_text(db: Session, file_content_hash: str) -> Optional[str]:
    cache_entry = db.query(DocumentTextCache).filter(
        DocumentTextCache.file_content_hash == file_content_hash
    ).first()
    if cache_entry:
        logger.info(f"[CACHE HIT] Document text found for content_hash={file_content_hash[:16]}...")
        return cache_entry.extracted_text
    logger.info(f"[CACHE MISS] No cached document text for content_hash={file_content_hash[:16]}...")
    return None


def store_document_text(db: Session, file_content_hash: str, extracted_text: str) -> None:
    try:
        cache_entry = DocumentTextCache(
            id=uuid.uuid4(),
            file_content_hash=file_content_hash,
            extracted_text=extracted_text,
            processed_at=datetime.now(timezone.utc),
        )
        db.add(cache_entry)
        db.commit()
        logger.info(f"[CACHE STORE] Stored document text for content_hash={file_content_hash[:16]}...")
    except Exception as e:
        db.rollback()
        logger.error(f"[CACHE ERROR] Failed to store document text: {str(e)}")
        raise
