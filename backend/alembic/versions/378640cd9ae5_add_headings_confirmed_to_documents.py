"""add_headings_confirmed_to_documents

Revision ID: 378640cd9ae5
Revises: 55cd193493bc
Create Date: 2026-01-26 13:52:20.372127

Phase 2.6: Add headings_confirmed flag to documents
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '378640cd9ae5'
down_revision: Union[str, None] = '55cd193493bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Phase 2.6: Add headings_confirmed column to documents table.
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('documents')} if 'documents' in inspector.get_table_names() else set()

    if 'headings_confirmed' not in existing_columns:
        # Use Integer for cross-database compatibility (0 = False, 1 = True)
        # This matches the model definition which uses Integer for SQLite and PostgreSQL compatibility
        op.add_column('documents', sa.Column('headings_confirmed', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """
    Remove headings_confirmed column from documents table.
    """
    inspector = sa.inspect(op.get_bind())
    existing_columns = {col['name'] for col in inspector.get_columns('documents')} if 'documents' in inspector.get_table_names() else set()

    if 'headings_confirmed' in existing_columns:
        op.drop_column('documents', 'headings_confirmed')
