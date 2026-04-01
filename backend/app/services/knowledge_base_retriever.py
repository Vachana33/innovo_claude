"""
Phase 4 — Knowledge Base Retriever

Two public responsibilities:
  1. index_document        — chunk a document's text and store embeddings
  2. retrieve_kb_context   — structured retrieval split by document category

Retrieval design:
  - Documents are split into three semantic categories:
      "example"    (or legacy "vorhabensbeschreibung") — past funding applications
      "guideline"  — funding program rules/requirements
      "domain"     — general technical / domain knowledge
  - Examples and guidelines are filtered by program_tag so results are
    program-specific. Domain knowledge is never filtered (it is universal).
  - Each category has its own top_k budget to give controlled composition.
  - All failures are logged and return empty lists — callers are never blocked.
"""
import logging
import os
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIM = 1536

# Per-category retrieval budgets
_TOP_K_EXAMPLES   = 3
_TOP_K_GUIDELINES = 3
_TOP_K_DOMAIN     = 2

_CHUNK_SIZE = 2000

# Legacy category name used before the "example" rename
_EXAMPLE_CATEGORIES = ["example", "vorhabensbeschreibung"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_openai_client():
    """Return an initialised OpenAI client or None if the key is missing."""
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("knowledge_base | OPENAI_API_KEY not set — skipping embedding")
        return None
    return OpenAI(api_key=api_key)


def _embed(texts: list[str], client) -> list[list[float]]:
    """
    Call the OpenAI embeddings endpoint for a batch of texts.
    Returns a list of float vectors in the same order as `texts`.
    Raises on API errors so the caller can decide how to handle them.
    """
    response = client.embeddings.create(
        model=_EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def _split_text(text: str) -> list[str]:
    """
    Split text into chunks of at most _CHUNK_SIZE characters.
    Splits preferentially on paragraph boundaries ("\n\n").
    Falls back to hard-splitting when paragraphs exceed _CHUNK_SIZE.
    """
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


def _retrieve_by_category(
    query_embedding: list[float],
    db: Session,
    categories: list[str],
    program_tag: Optional[str],
    top_k: int,
) -> list[dict]:
    """
    Cosine-distance search filtered to specific document categories.

    If program_tag is given and returns no results, falls back to the same
    category search without the tag (so you still get something useful when
    KB documents haven't been tagged yet).

    Returns a list of dicts: {chunk_text, category, source_filename}.
    Returns [] on any error.
    """
    from app.models import KnowledgeBaseChunk, KnowledgeBaseDocument

    def _run_query(tag: Optional[str]) -> list[dict]:
        q = (
            db.query(KnowledgeBaseChunk, KnowledgeBaseDocument)
            .join(KnowledgeBaseDocument,
                  KnowledgeBaseChunk.document_id == KnowledgeBaseDocument.id)
            .filter(KnowledgeBaseDocument.category.in_(categories))
        )
        if tag:
            q = q.filter(KnowledgeBaseDocument.program_tag == tag)

        rows = (
            q.order_by(KnowledgeBaseChunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
            .all()
        )
        return [
            {
                "chunk_text": chunk.chunk_text,
                "category": doc.category,
                "source_filename": doc.filename,
            }
            for chunk, doc in rows
        ]

    try:
        results = _run_query(program_tag)
        # Fallback: if a tag was given but returned nothing, try unfiltered
        if not results and program_tag:
            logger.info(
                "knowledge_base | _retrieve_by_category: no results for tag=%s categories=%s — trying unfiltered",
                program_tag, categories,
            )
            results = _run_query(None)
        return results
    except Exception:
        logger.exception(
            "knowledge_base | _retrieve_by_category failed categories=%s program_tag=%s",
            categories, program_tag,
        )
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def index_document(document_id: UUID | str, db: Session) -> None:
    """
    Load the text for a KnowledgeBaseDocument, split it into chunks,
    generate embeddings and persist KnowledgeBaseChunk rows.

    Idempotent: existing chunks for this document are deleted first so
    re-indexing after a content change is safe.

    Failures are logged; the document row is never deleted on failure.
    """
    from app.models import KnowledgeBaseDocument, KnowledgeBaseChunk
    from app.file_storage import download_from_supabase_storage
    from app.document_extraction import extract_document_text

    try:
        doc = db.query(KnowledgeBaseDocument).filter(
            KnowledgeBaseDocument.id == document_id
        ).first()
        if not doc:
            logger.error("knowledge_base | index_document: document_id=%s not found", document_id)
            return

        file_bytes = download_from_supabase_storage(doc.file.storage_path)
        if not file_bytes:
            logger.error("knowledge_base | index_document: could not download file document_id=%s", document_id)
            return

        file_type = doc.file.file_type or "pdf"
        content_hash = doc.file.content_hash
        text = extract_document_text(file_bytes, content_hash, file_type, db)
        if not text:
            logger.error("knowledge_base | index_document: text extraction returned nothing document_id=%s", document_id)
            return

        chunks = _split_text(text)
        if not chunks:
            logger.warning("knowledge_base | index_document: no chunks produced document_id=%s", document_id)
            return

        client = _get_openai_client()
        if not client:
            return

        try:
            embeddings = _embed(chunks, client)
        except Exception:
            logger.exception("knowledge_base | index_document: embedding API error document_id=%s", document_id)
            return

        # Delete existing chunks (idempotent re-index)
        db.query(KnowledgeBaseChunk).filter(
            KnowledgeBaseChunk.document_id == doc.id
        ).delete(synchronize_session=False)

        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            db.add(KnowledgeBaseChunk(
                document_id=doc.id,
                chunk_text=chunk_text,
                embedding=embedding,
                chunk_index=idx,
            ))

        db.commit()
        logger.info(
            "knowledge_base | index_document: document_id=%s category=%s indexed %d chunks",
            document_id, doc.category, len(chunks),
        )

    except Exception:
        logger.exception("knowledge_base | index_document: unhandled error document_id=%s", document_id)
        db.rollback()


def retrieve_kb_context(
    query: str,
    db: Session,
    program_tag: Optional[str] = None,
) -> dict:
    """
    Structured retrieval split by document category.

    Returns:
        {
            "examples":   up to 3 chunks from example/vorhabensbeschreibung docs
                          (filtered by program_tag; falls back to unfiltered)
            "guidelines": up to 3 chunks from guideline docs
                          (filtered by program_tag; falls back to unfiltered)
            "domain":     up to 2 chunks from domain docs
                          (never filtered by program_tag — domain knowledge is universal)
        }

    program_tag convention:
        The tag on KB documents is a free-text field set by the admin at upload time.
        To get program-specific results, it must match the FundingProgram.title exactly.
        If no tagged documents exist the fallback (unfiltered per category) is used.

    Returns the empty-dict structure on any error so callers are never blocked.
    """
    from app.models import KnowledgeBaseChunk

    empty = {"examples": [], "guidelines": [], "domain": []}

    try:
        chunk_count = db.query(KnowledgeBaseChunk).count()
    except Exception:
        logger.exception("knowledge_base | retrieve_kb_context: could not count chunks")
        return empty

    if chunk_count == 0:
        return empty

    client = _get_openai_client()
    if not client:
        return empty

    try:
        query_embedding = _embed([query], client)[0]
    except Exception:
        logger.exception("knowledge_base | retrieve_kb_context: embedding API error query_len=%d", len(query))
        return empty

    results = {
        "examples": _retrieve_by_category(
            query_embedding, db,
            categories=_EXAMPLE_CATEGORIES,  # support legacy "vorhabensbeschreibung" name
            program_tag=program_tag,
            top_k=_TOP_K_EXAMPLES,
        ),
        "guidelines": _retrieve_by_category(
            query_embedding, db,
            categories=["guideline"],
            program_tag=program_tag,
            top_k=_TOP_K_GUIDELINES,
        ),
        "domain": _retrieve_by_category(
            query_embedding, db,
            categories=["domain"],
            program_tag=None,  # domain is always unfiltered
            top_k=_TOP_K_DOMAIN,
        ),
    }

    total = sum(len(v) for v in results.values())
    logger.info(
        "knowledge_base | retrieve_kb_context: program_tag=%s total_chunks=%d "
        "(examples=%d guidelines=%d domain=%d)",
        program_tag, total,
        len(results["examples"]), len(results["guidelines"]), len(results["domain"]),
    )
    return results
