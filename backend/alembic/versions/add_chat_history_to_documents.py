"""add_chat_history_to_documents

Revision ID: add_chat_history
Revises: 1bdfd9e377ca
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_chat_history'
down_revision: Union[str, None] = '1bdfd9e377ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add chat_history column to documents table
    # Use JSON type for PostgreSQL, or Text for SQLite
    op.add_column('documents', sa.Column('chat_history', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove chat_history column
    op.drop_column('documents', 'chat_history')
