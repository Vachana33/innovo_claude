"""
Phase 4 — Funding Program Source Scraper

Public API:
  fetch_and_index(source_id, db)  — scrape one URL and (re-)index its text
  scrape_all_sources(db)          — iterate every non-failed source and call fetch_and_index
  scrape_all_sources_task()       — entry point for the APScheduler cron job (own DB session)

Design:
  - The scraped text is stored as a KnowledgeBaseDocument (category="guideline",
    source_id=<FundingProgramSource.id>, file_id=NULL).
  - One KnowledgeBaseDocument per FundingProgramSource.  On re-scrape the existing
    document's chunks are deleted and rebuilt; the document row is reused.
  - Content-hash deduplication: if the page text is identical to the last scrape,
    the indexing step is skipped.
  - Failures set status="failed" and store the error message; they never propagate
    so the scheduler loop continues with the next source.
"""
import hashlib
import logging
import os
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 2000
_SCRAPE_TIMEOUT = 30           # seconds
_MIN_TEXT_LENGTH = 50          # skip pages that return almost nothing


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_text(url: str) -> str:
    """
    Fetch a URL and return its visible text via BeautifulSoup.
    Raises on HTTP errors or timeouts — callers are expected to catch.
    """
    import requests
    from bs4 import BeautifulSoup

    headers = {"User-Agent": "Innovo-KnowledgeBase-Bot/1.0"}
    resp = requests.get(url, timeout=_SCRAPE_TIMEOUT, headers=headers)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove common navigation / boilerplate elements
    for tag in soup(["script", "style", "nav", "header", "footer",
                      "aside", "noscript", "form"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    # Collapse excessive blank lines
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = "\n".join(ln for ln in lines if ln)
    return cleaned


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_text(text: str) -> list[str]:
    """Paragraph-aware chunker reused from the KB retriever convention."""
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 <= _CHUNK_SIZE:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
            while len(para) > _CHUNK_SIZE:
                chunks.append(para[:_CHUNK_SIZE])
                para = para[_CHUNK_SIZE:]
            current = para

    if current:
        chunks.append(current)
    return chunks


def _get_openai_client():
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("funding_scraper | OPENAI_API_KEY not set — skipping embedding")
        return None
    return OpenAI(api_key=api_key)


def _embed(texts: list[str], client) -> list[list[float]]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


def _get_or_create_kb_document(source_id: UUID, url: str,
                                program_title: str, db: Session):
    """
    Return the KnowledgeBaseDocument tied to this source.
    Creates one if it doesn't exist yet.
    """
    from app.models import KnowledgeBaseDocument

    doc = db.query(KnowledgeBaseDocument).filter(
        KnowledgeBaseDocument.source_id == source_id
    ).first()

    if doc is None:
        doc = KnowledgeBaseDocument(
            filename=url,
            category="guideline",
            program_tag=program_title,
            file_id=None,
            source_id=source_id,
            uploaded_by="system",
        )
        db.add(doc)
        db.flush()   # get doc.id without committing

    return doc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_and_index(source_id: UUID | str, db: Session) -> None:
    """
    Scrape one FundingProgramSource URL and index its text into the knowledge base.

    Steps:
      1. Load the source row; set status = "scraping"
      2. Fetch the page and extract text
      3. Compare SHA-256 hash to source.content_hash (skip if unchanged)
      4. Get or create the associated KnowledgeBaseDocument
      5. Delete stale chunks
      6. Chunk, embed, and persist new KnowledgeBaseChunk rows
      7. Update source.last_scraped_at / content_hash / status
      8. On any error: set status = "failed", store error_message
    """
    from app.models import FundingProgramSource, KnowledgeBaseChunk
    from datetime import datetime, timezone

    source = db.query(FundingProgramSource).filter(
        FundingProgramSource.id == source_id
    ).first()

    if not source:
        logger.error("funding_scraper | source_id=%s not found", source_id)
        return

    logger.info(
        "funding_scraper | starting fetch source_id=%s url=%s", source_id, source.url
    )
    source.status = "scraping"
    db.commit()

    try:
        # --- Step 1: fetch page text ---
        text = _fetch_text(source.url)
        if len(text) < _MIN_TEXT_LENGTH:
            raise ValueError(
                f"Page returned too little text ({len(text)} chars). "
                "It may be JS-rendered or require authentication."
            )

        # --- Step 2: change detection ---
        new_hash = _sha256(text)
        if new_hash == source.content_hash:
            logger.info(
                "funding_scraper | no change detected source_id=%s — skipping re-index",
                source_id,
            )
            source.status = "done"
            source.last_scraped_at = datetime.now(tz=timezone.utc)
            db.commit()
            return

        # --- Step 3: get/create KB document ---
        program_title = (
            source.funding_program.title if source.funding_program else ""
        )
        kb_doc = _get_or_create_kb_document(
            source.id, source.url, program_title, db
        )

        # --- Step 4: delete stale chunks ---
        db.query(KnowledgeBaseChunk).filter(
            KnowledgeBaseChunk.document_id == kb_doc.id
        ).delete(synchronize_session=False)

        # --- Step 5: chunk + embed ---
        chunks = _split_text(text)
        if not chunks:
            raise ValueError("Text splitting produced no chunks.")

        client = _get_openai_client()
        if not client:
            raise RuntimeError("OpenAI client unavailable — cannot embed chunks.")

        embeddings = _embed(chunks, client)

        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            db.add(KnowledgeBaseChunk(
                document_id=kb_doc.id,
                chunk_text=chunk_text,
                embedding=embedding,
                chunk_index=idx,
            ))

        # --- Step 6: update source row ---
        source.content_hash = new_hash
        source.last_scraped_at = datetime.now(tz=timezone.utc)
        source.status = "done"
        source.error_message = None
        db.commit()

        logger.info(
            "funding_scraper | completed source_id=%s url=%s chunks=%d",
            source_id, source.url, len(chunks),
        )

    except Exception as exc:
        db.rollback()
        logger.exception(
            "funding_scraper | failed source_id=%s url=%s error=%s",
            source_id, source.url, str(exc),
        )
        try:
            source.status = "failed"
            source.error_message = str(exc)[:500]
            db.commit()
        except Exception:
            db.rollback()


def scrape_all_sources(db: Session) -> None:
    """
    Iterate every FundingProgramSource that is not currently scraping
    and call fetch_and_index on each.  Intended for the weekly cron job.
    """
    from app.models import FundingProgramSource

    sources = db.query(FundingProgramSource).filter(
        FundingProgramSource.status != "scraping"
    ).all()

    logger.info("funding_scraper | scrape_all_sources: %d sources to process", len(sources))
    for source in sources:
        fetch_and_index(source.id, db)


def scrape_all_sources_task() -> None:
    """
    APScheduler entry point.
    Opens its own DB session so the scheduler thread is independent of any
    request context.
    """
    from app.database import SessionLocal

    logger.info("funding_scraper | scheduled scrape_all_sources_task starting")
    db = SessionLocal()
    try:
        scrape_all_sources(db)
        logger.info("funding_scraper | scheduled scrape_all_sources_task completed")
    except Exception:
        logger.exception("funding_scraper | scheduled scrape_all_sources_task failed")
    finally:
        db.close()
