"""Add funding_program_sources table and update knowledge_base_documents

Revision ID: g5h6i7j8k9l0
Revises: f4a5b6c7d8e9
Create Date: 2026-03-25

Changes:
  - Create funding_program_sources table (URL-based scrape sources per program)
  - Make knowledge_base_documents.file_id nullable (scrape-sourced docs have no File)
  - Add knowledge_base_documents.source_id FK → funding_program_sources
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'g5h6i7j8k9l0'
down_revision: Union[str, None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create funding_program_sources
    # ------------------------------------------------------------------
    op.create_table(
        'funding_program_sources',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('funding_program_id', sa.Integer(),
                  sa.ForeignKey('funding_programs.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('last_scraped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('content_hash', sa.String(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(
        'ix_funding_program_sources_funding_program_id',
        'funding_program_sources', ['funding_program_id'],
    )

    # ------------------------------------------------------------------
    # 2. Make knowledge_base_documents.file_id nullable
    #    (scrape-sourced documents have no backing File record)
    # ------------------------------------------------------------------
    op.alter_column(
        'knowledge_base_documents', 'file_id',
        existing_type=UUID(as_uuid=True),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # 3. Add source_id FK on knowledge_base_documents
    # ------------------------------------------------------------------
    op.add_column(
        'knowledge_base_documents',
        sa.Column('source_id', UUID(as_uuid=True),
                  sa.ForeignKey('funding_program_sources.id', ondelete='CASCADE'),
                  nullable=True),
    )
    op.create_index(
        'ix_knowledge_base_documents_source_id',
        'knowledge_base_documents', ['source_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_knowledge_base_documents_source_id',
                  table_name='knowledge_base_documents')
    op.drop_column('knowledge_base_documents', 'source_id')

    op.alter_column(
        'knowledge_base_documents', 'file_id',
        existing_type=UUID(as_uuid=True),
        nullable=False,
    )

    op.drop_index('ix_funding_program_sources_funding_program_id',
                  table_name='funding_program_sources')
    op.drop_table('funding_program_sources')
