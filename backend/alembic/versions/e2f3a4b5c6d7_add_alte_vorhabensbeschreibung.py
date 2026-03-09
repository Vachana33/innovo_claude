"""add_alte_vorhabensbeschreibung

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-01-30 17:00:00.000000

Create Alte Vorhabensbeschreibung tables for historical writing style extraction.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create alte_vorhabensbeschreibung_documents and alte_vorhabensbeschreibung_style_profile tables.
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # Create alte_vorhabensbeschreibung_documents table
    if 'alte_vorhabensbeschreibung_documents' not in existing_tables:
        if is_sqlite:
            op.create_table(
                'alte_vorhabensbeschreibung_documents',
                sa.Column('id', sa.String(36), primary_key=True, nullable=False),
                sa.Column('file_id', sa.String(36), sa.ForeignKey('files.id'), nullable=False, index=True),
                sa.Column('original_filename', sa.String(), nullable=False),
                sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('uploaded_by', sa.String(), sa.ForeignKey('users.email'), nullable=False),
            )
            op.create_index('ix_alte_vorhabensbeschreibung_documents_file_id', 'alte_vorhabensbeschreibung_documents', ['file_id'], unique=False)
        else:
            op.create_table(
                'alte_vorhabensbeschreibung_documents',
                sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()'), nullable=False),
                sa.Column('file_id', UUID(as_uuid=True), sa.ForeignKey('files.id'), nullable=False),
                sa.Column('original_filename', sa.String(), nullable=False),
                sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('uploaded_by', sa.String(), sa.ForeignKey('users.email'), nullable=False),
            )
            # Check if index exists before creating
            existing_indexes = [idx['name'] for idx in inspector.get_indexes('alte_vorhabensbeschreibung_documents')]
            if 'ix_alte_vorhabensbeschreibung_documents_file_id' not in existing_indexes:
                op.create_index('ix_alte_vorhabensbeschreibung_documents_file_id', 'alte_vorhabensbeschreibung_documents', ['file_id'], unique=False)
            if 'ix_alte_vorhabensbeschreibung_documents_uploaded_by' not in existing_indexes:
                op.create_index('ix_alte_vorhabensbeschreibung_documents_uploaded_by', 'alte_vorhabensbeschreibung_documents', ['uploaded_by'], unique=False)
    else:
        # Table exists, check if indexes need to be created
        if not is_sqlite:
            existing_indexes = [idx['name'] for idx in inspector.get_indexes('alte_vorhabensbeschreibung_documents')]
            if 'ix_alte_vorhabensbeschreibung_documents_file_id' not in existing_indexes:
                op.create_index('ix_alte_vorhabensbeschreibung_documents_file_id', 'alte_vorhabensbeschreibung_documents', ['file_id'], unique=False)
            if 'ix_alte_vorhabensbeschreibung_documents_uploaded_by' not in existing_indexes:
                op.create_index('ix_alte_vorhabensbeschreibung_documents_uploaded_by', 'alte_vorhabensbeschreibung_documents', ['uploaded_by'], unique=False)
    
    # Create alte_vorhabensbeschreibung_style_profile table
    if 'alte_vorhabensbeschreibung_style_profile' not in existing_tables:
        if is_sqlite:
            op.create_table(
                'alte_vorhabensbeschreibung_style_profile',
                sa.Column('id', sa.String(36), primary_key=True, nullable=False),
                sa.Column('combined_hash', sa.Text(), unique=True, nullable=False, index=True),
                sa.Column('style_summary_json', sa.Text(), nullable=False),  # SQLite stores JSON as TEXT
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            )
            op.create_index('ix_alte_vorhabensbeschreibung_style_profile_combined_hash', 'alte_vorhabensbeschreibung_style_profile', ['combined_hash'], unique=True)
        else:
            op.create_table(
                'alte_vorhabensbeschreibung_style_profile',
                sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()'), nullable=False),
                sa.Column('combined_hash', sa.Text(), unique=True, nullable=False),
                sa.Column('style_summary_json', JSONB(), nullable=False),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            )
            # Check if index exists before creating
            existing_indexes = [idx['name'] for idx in inspector.get_indexes('alte_vorhabensbeschreibung_style_profile')]
            if 'ix_alte_vorhabensbeschreibung_style_profile_combined_hash' not in existing_indexes:
                op.create_index('ix_alte_vorhabensbeschreibung_style_profile_combined_hash', 'alte_vorhabensbeschreibung_style_profile', ['combined_hash'], unique=True)
    else:
        # Table exists, check if indexes need to be created
        if not is_sqlite:
            existing_indexes = [idx['name'] for idx in inspector.get_indexes('alte_vorhabensbeschreibung_style_profile')]
            if 'ix_alte_vorhabensbeschreibung_style_profile_combined_hash' not in existing_indexes:
                op.create_index('ix_alte_vorhabensbeschreibung_style_profile_combined_hash', 'alte_vorhabensbeschreibung_style_profile', ['combined_hash'], unique=True)


def downgrade() -> None:
    """
    Drop alte_vorhabensbeschreibung tables.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if 'alte_vorhabensbeschreibung_style_profile' in existing_tables:
        op.drop_index('ix_alte_vorhabensbeschreibung_style_profile_combined_hash', table_name='alte_vorhabensbeschreibung_style_profile')
        op.drop_table('alte_vorhabensbeschreibung_style_profile')
    
    if 'alte_vorhabensbeschreibung_documents' in existing_tables:
        op.drop_index('ix_alte_vorhabensbeschreibung_documents_file_id', table_name='alte_vorhabensbeschreibung_documents')
        op.drop_table('alte_vorhabensbeschreibung_documents')
