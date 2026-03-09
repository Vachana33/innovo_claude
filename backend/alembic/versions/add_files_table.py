"""add_files_table

Revision ID: add_files_table
Revises: 5118cacae937
Create Date: 2026-01-XX XX:XX:XX.XXXXXX

Phase 1: Infrastructure & Deduplication
Creates files table for hash-based file deduplication.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_files_table'
down_revision: Union[str, None] = '5118cacae937'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create files table for hash-based file deduplication.
    - id: UUID primary key (String for SQLite, UUID for PostgreSQL)
    - content_hash: TEXT, UNIQUE, NOT NULL (SHA256 hash)
    - file_type: TEXT (e.g., "audio", "pdf", "docx")
    - storage_path: TEXT, NOT NULL (path in Supabase Storage)
    - size_bytes: INTEGER, NOT NULL
    - created_at: TIMESTAMP with timezone, default now
    """
    # Check if we're using SQLite (which has limited ALTER TABLE support)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    # Check if table already exists (in case of partial migration)
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'files' in existing_tables:
        # Table already exists, skip creation
        return

    if is_sqlite:
        # SQLite: Create table with unique constraint inline (SQLite doesn't support ALTER for constraints)
        op.create_table(
            'files',
            sa.Column('id', sa.String(36), primary_key=True, nullable=False),
            sa.Column('content_hash', sa.Text(), nullable=False, unique=True),  # Unique constraint inline
            sa.Column('file_type', sa.Text(), nullable=True),
            sa.Column('storage_path', sa.Text(), nullable=False),
            sa.Column('size_bytes', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        # Create index on content_hash for fast lookups
        op.create_index('ix_files_content_hash', 'files', ['content_hash'])
    else:
        # PostgreSQL: Use UUID type
        op.create_table(
            'files',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('content_hash', sa.Text(), nullable=False),
            sa.Column('file_type', sa.Text(), nullable=True),
            sa.Column('storage_path', sa.Text(), nullable=False),
            sa.Column('size_bytes', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        # Create unique constraint on content_hash
        op.create_unique_constraint('uq_files_content_hash', 'files', ['content_hash'])
        # Create index on content_hash for fast lookups
        op.create_index('ix_files_content_hash', 'files', ['content_hash'])


def downgrade() -> None:
    """
    Remove files table.
    """
    # Check if table exists before dropping (safe downgrade)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'files' not in existing_tables:
        # Table doesn't exist, skip
        return

    # Check database dialect
    is_sqlite = bind.dialect.name == 'sqlite'

    # Drop indexes first
    try:
        op.drop_index('ix_files_content_hash', table_name='files')
    except Exception:
        # Index might not exist, continue
        pass

    # Drop unique constraint only for PostgreSQL (SQLite uses inline unique constraint)
    if not is_sqlite:
        try:
            op.drop_constraint('uq_files_content_hash', 'files', type_='unique')
        except Exception:
            # Constraint might not exist, continue
            pass

    # Drop table
    op.drop_table('files')
