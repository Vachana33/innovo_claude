"""add_processing_cache_tables

Revision ID: add_processing_cache_tables
Revises: add_files_table
Create Date: 2026-01-XX XX:XX:XX.XXXXXX

Phase 2: Raw Processing Cache
Creates cache tables for audio transcripts, website text, and document text extraction.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_processing_cache_tables'
down_revision: Union[str, None] = 'add_files_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create cache tables for raw processing outputs:
    - audio_transcript_cache: Cached Whisper transcripts keyed by file content_hash
    - website_text_cache: Cached website text keyed by normalized URL hash
    - document_text_cache: Cached document text keyed by file content_hash
    """
    # Check if we're using SQLite (which has limited ALTER TABLE support)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    # Check if tables already exist (in case of partial migration)
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Create audio_transcript_cache table
    if 'audio_transcript_cache' not in existing_tables:
        if is_sqlite:
            op.create_table(
                'audio_transcript_cache',
                sa.Column('id', sa.String(36), primary_key=True, nullable=False),
                sa.Column('file_content_hash', sa.Text(), nullable=False, unique=True),
                sa.Column('transcript_text', sa.Text(), nullable=False),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            )
            op.create_index('ix_audio_transcript_cache_file_content_hash', 'audio_transcript_cache', ['file_content_hash'])
        else:
            op.create_table(
                'audio_transcript_cache',
                sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
                sa.Column('file_content_hash', sa.Text(), nullable=False),
                sa.Column('transcript_text', sa.Text(), nullable=False),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            )
            op.create_unique_constraint('uq_audio_transcript_cache_file_content_hash', 'audio_transcript_cache', ['file_content_hash'])
            op.create_index('ix_audio_transcript_cache_file_content_hash', 'audio_transcript_cache', ['file_content_hash'])

    # Create website_text_cache table
    if 'website_text_cache' not in existing_tables:
        if is_sqlite:
            op.create_table(
                'website_text_cache',
                sa.Column('id', sa.String(36), primary_key=True, nullable=False),
                sa.Column('url_hash', sa.Text(), nullable=False, unique=True),
                sa.Column('normalized_url', sa.Text(), nullable=False),
                sa.Column('website_text', sa.Text(), nullable=False),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            )
            op.create_index('ix_website_text_cache_url_hash', 'website_text_cache', ['url_hash'])
        else:
            op.create_table(
                'website_text_cache',
                sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
                sa.Column('url_hash', sa.Text(), nullable=False),
                sa.Column('normalized_url', sa.Text(), nullable=False),
                sa.Column('website_text', sa.Text(), nullable=False),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            )
            op.create_unique_constraint('uq_website_text_cache_url_hash', 'website_text_cache', ['url_hash'])
            op.create_index('ix_website_text_cache_url_hash', 'website_text_cache', ['url_hash'])

    # Create document_text_cache table
    if 'document_text_cache' not in existing_tables:
        if is_sqlite:
            op.create_table(
                'document_text_cache',
                sa.Column('id', sa.String(36), primary_key=True, nullable=False),
                sa.Column('file_content_hash', sa.Text(), nullable=False, unique=True),
                sa.Column('extracted_text', sa.Text(), nullable=False),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            )
            op.create_index('ix_document_text_cache_file_content_hash', 'document_text_cache', ['file_content_hash'])
        else:
            op.create_table(
                'document_text_cache',
                sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
                sa.Column('file_content_hash', sa.Text(), nullable=False),
                sa.Column('extracted_text', sa.Text(), nullable=False),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            )
            op.create_unique_constraint('uq_document_text_cache_file_content_hash', 'document_text_cache', ['file_content_hash'])
            op.create_index('ix_document_text_cache_file_content_hash', 'document_text_cache', ['file_content_hash'])


def downgrade() -> None:
    """
    Remove cache tables.
    """
    # Check if tables exist before dropping (safe downgrade)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'document_text_cache' in existing_tables:
        op.drop_index('ix_document_text_cache_file_content_hash', table_name='document_text_cache')
        if bind.dialect.name != 'sqlite':
            op.drop_constraint('uq_document_text_cache_file_content_hash', 'document_text_cache', type_='unique')
        op.drop_table('document_text_cache')

    if 'website_text_cache' in existing_tables:
        op.drop_index('ix_website_text_cache_url_hash', table_name='website_text_cache')
        if bind.dialect.name != 'sqlite':
            op.drop_constraint('uq_website_text_cache_url_hash', 'website_text_cache', type_='unique')
        op.drop_table('website_text_cache')

    if 'audio_transcript_cache' in existing_tables:
        op.drop_index('ix_audio_transcript_cache_file_content_hash', table_name='audio_transcript_cache')
        if bind.dialect.name != 'sqlite':
            op.drop_constraint('uq_audio_transcript_cache_file_content_hash', 'audio_transcript_cache', type_='unique')
        op.drop_table('audio_transcript_cache')
