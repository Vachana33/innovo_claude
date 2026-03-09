"""add_funding_program_guidelines_summary

Revision ID: c9d0e1f2a3b4
Revises: b7c8d9e0f1a2
Create Date: 2026-01-30 14:00:00.000000

Create funding_program_guidelines_summary table for storing structured rules
extracted from guideline documents.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create funding_program_guidelines_summary table.
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'funding_program_guidelines_summary' in existing_tables:
        # Table already exists, skip creation
        return

    if is_sqlite:
        # SQLite: Use String for UUID and Text for JSON
        op.create_table(
            'funding_program_guidelines_summary',
            sa.Column('id', sa.String(36), primary_key=True, nullable=False),
            sa.Column('funding_program_id', sa.Integer(), nullable=False),
            sa.Column('rules_json', sa.Text(), nullable=False),
            sa.Column('source_file_hash', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_funding_program_guidelines_summary_id', 'funding_program_guidelines_summary', ['id'])
        op.create_index('ix_funding_program_guidelines_summary_funding_program_id', 'funding_program_guidelines_summary', ['funding_program_id'], unique=True)
        op.create_foreign_key(
            'fk_funding_program_guidelines_summary_funding_program_id',
            'funding_program_guidelines_summary',
            'funding_programs',
            ['funding_program_id'],
            ['id']
        )
    else:
        # PostgreSQL: Use UUID and JSONB
        op.create_table(
            'funding_program_guidelines_summary',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('funding_program_id', sa.Integer(), nullable=False, unique=True),
            sa.Column('rules_json', JSONB, nullable=False),
            sa.Column('source_file_hash', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_funding_program_guidelines_summary_id', 'funding_program_guidelines_summary', ['id'])
        op.create_index('ix_funding_program_guidelines_summary_funding_program_id', 'funding_program_guidelines_summary', ['funding_program_id'], unique=True)
        op.create_foreign_key(
            'fk_funding_program_guidelines_summary_funding_program_id',
            'funding_program_guidelines_summary',
            'funding_programs',
            ['funding_program_id'],
            ['id']
        )


def downgrade() -> None:
    """
    Drop funding_program_guidelines_summary table.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'funding_program_guidelines_summary' in existing_tables:
        if bind.dialect.name != 'sqlite':
            op.drop_constraint('fk_funding_program_guidelines_summary_funding_program_id', 'funding_program_guidelines_summary', type_='foreignkey')
        op.drop_index('ix_funding_program_guidelines_summary_funding_program_id', table_name='funding_program_guidelines_summary')
        op.drop_index('ix_funding_program_guidelines_summary_id', table_name='funding_program_guidelines_summary')
        op.drop_table('funding_program_guidelines_summary')
