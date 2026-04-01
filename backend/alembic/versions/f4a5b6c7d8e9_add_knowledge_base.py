"""Add knowledge base tables (Phase 4)

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-03-23

Creates:
  - knowledge_base_documents: admin-uploaded documents with metadata
  - knowledge_base_chunks: text chunks with pgvector embeddings

Uses raw SQL for the vector column because SQLAlchemy's type system does
not include VECTOR natively — pgvector provides it via the Python package
but we keep the migration self-contained with raw DDL.

Preflight: pgvector extension must be available on the PostgreSQL server.
In Supabase it is available by default. If running locally:
    CREATE EXTENSION IF NOT EXISTS vector;

The ivfflat index is safe to create on an empty table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Embedding dimensions must match the OpenAI model used in the service layer.
# text-embedding-3-small produces 1536-dimensional vectors.
EMBEDDING_DIM = 1536


def upgrade() -> None:
    # Enable pgvector extension (idempotent — safe to run multiple times)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- knowledge_base_documents ---
    op.create_table(
        'knowledge_base_documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),   # e.g. "vorhabensbeschreibung", "domain", "other"
        sa.Column('program_tag', sa.String(), nullable=True), # optional filter tag for retrieval
        sa.Column('file_id', UUID(as_uuid=True),
                  sa.ForeignKey('files.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('uploaded_by', sa.String(),
                  sa.ForeignKey('users.email', ondelete='RESTRICT'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_knowledge_base_documents_category',
                    'knowledge_base_documents', ['category'])
    op.create_index('ix_knowledge_base_documents_program_tag',
                    'knowledge_base_documents', ['program_tag'])

    # --- knowledge_base_chunks ---
    # Vector column must be added via raw SQL; the rest uses SA types.
    op.create_table(
        'knowledge_base_chunks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', UUID(as_uuid=True),
                  sa.ForeignKey('knowledge_base_documents.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )
    # Add vector column separately — DDL requires pgvector extension to be active
    op.execute(
        f"ALTER TABLE knowledge_base_chunks "
        f"ADD COLUMN embedding vector({EMBEDDING_DIM})"
    )
    op.create_index('ix_knowledge_base_chunks_document_id',
                    'knowledge_base_chunks', ['document_id'])
    # ivfflat index for approximate nearest-neighbour search (cosine distance)
    op.execute(
        "CREATE INDEX ix_knowledge_base_chunks_embedding "
        "ON knowledge_base_chunks "
        f"USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_index('ix_knowledge_base_chunks_embedding',
                  table_name='knowledge_base_chunks')
    op.drop_index('ix_knowledge_base_chunks_document_id',
                  table_name='knowledge_base_chunks')
    op.drop_table('knowledge_base_chunks')

    op.drop_index('ix_knowledge_base_documents_program_tag',
                  table_name='knowledge_base_documents')
    op.drop_index('ix_knowledge_base_documents_category',
                  table_name='knowledge_base_documents')
    op.drop_table('knowledge_base_documents')
    # Note: we do NOT drop the vector extension — it may be used by other tables.
