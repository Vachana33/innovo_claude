"""
Phase 4 — Knowledge Base Retriever
"""
import logging
import os
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIM = 1536

_TOP_K_EXAMPLES = 3
_TOP_K_GUIDELINES = 3
_TOP_K_DOMAIN = 2

_CHUNK_SIZE = 2000

_EXAMPLE_CATEGORIES = ["example", "vorhabensbeschreibung"]


def _get_openai_client():
    from openai import OpenAI  # noqa: PLC0415
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("knowledge_base | OPENAI_API_KEY not set — skipping embedding")
        return None
    return OpenAI(api_key=api_key)


def _embed(texts: list[str], client) -> list[list[float]]:
    response = client.embeddings.create(model=_EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def _split_text(text: str) -> list[str]:
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
    from innovo_backend.shared.models import KnowledgeBaseChunk, KnowledgeBaseDocument  # noqa: PLC0415

    def _run_query(tag: Optional[str]) -> list[dict]:
        q = (
            db.query(KnowledgeBaseChunk, KnowledgeBaseDocument)
            .join(KnowledgeBaseDocument, KnowledgeBaseChunk.document_id == KnowledgeBaseDocument.id)
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
        if not results and program_tag:
            logger.info(
                "knowledge_base | _retrieve_by_category: no results for tag=%s — trying unfiltered",
                program_tag,
            )
            results = _run_query(None)
        return results
    except Exception:
        logger.exception(
            "knowledge_base | _retrieve_by_category failed categories=%s program_tag=%s",
            categories, program_tag,
        )
        return []


def index_document(document_id: UUID | str, db: Session) -> None:
    from innovo_backend.shared.models import KnowledgeBaseDocument, KnowledgeBaseChunk  # noqa: PLC0415
    from innovo_backend.shared.file_storage import download_from_supabase_storage  # noqa: PLC0415
    from innovo_backend.shared.document_extraction import extract_document_text  # noqa: PLC0415

    try:
        doc = db.query(KnowledgeBaseDocument).filter(KnowledgeBaseDocument.id == document_id).first()
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
    from innovo_backend.shared.models import KnowledgeBaseChunk  # noqa: PLC0415

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
            categories=_EXAMPLE_CATEGORIES,
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
            program_tag=None,
            top_k=_TOP_K_DOMAIN,
        ),
    }

    total = sum(len(v) for v in results.values())
    logger.info(
        "knowledge_base | retrieve_kb_context: program_tag=%s total_chunks=%d",
        program_tag, total,
    )
    return results
