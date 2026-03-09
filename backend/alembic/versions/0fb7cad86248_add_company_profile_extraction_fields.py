"""add_company_profile_extraction_fields

Revision ID: 0fb7cad86248
Revises: f5c86d23bbfc
Create Date: 2026-01-20 14:14:29.108691

Phase 2A: Schema extension for Extract → Store → Reference flow.
Adds structured company_profile JSON field and extraction metadata.
All fields are nullable for backward compatibility.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fb7cad86248'
down_revision: Union[str, None] = 'f5c86d23bbfc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add company_profile extraction fields to companies table.
    - company_profile: JSON field for structured extracted company information
    - extraction_status: String field ("pending" | "extracted" | "failed")
    - extracted_at: DateTime field for extraction timestamp

    All fields are nullable for backward compatibility.
    """
    # Check if we're using SQLite (which has limited ALTER TABLE support)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    # Check if columns already exist (in case of partial migration)
    inspector = sa.inspect(bind)
    companies_columns = [col['name'] for col in inspector.get_columns('companies')]

    # Add company_profile JSON column
    if 'company_profile' not in companies_columns:
        if is_sqlite:
            # SQLite doesn't have native JSON, use TEXT
            op.add_column('companies', sa.Column('company_profile', sa.Text(), nullable=True))
        else:
            # PostgreSQL and other databases support JSON
            op.add_column('companies', sa.Column('company_profile', sa.JSON(), nullable=True))

    # Add extraction_status column
    if 'extraction_status' not in companies_columns:
        op.add_column('companies', sa.Column('extraction_status', sa.String(), nullable=True))

    # Add extracted_at timestamp column
    if 'extracted_at' not in companies_columns:
        op.add_column('companies', sa.Column('extracted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """
    Remove company_profile extraction fields from companies table.
    """
    # Check if columns exist before dropping (safe downgrade)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    companies_columns = [col['name'] for col in inspector.get_columns('companies')]

    if 'extracted_at' in companies_columns:
        op.drop_column('companies', 'extracted_at')

    if 'extraction_status' in companies_columns:
        op.drop_column('companies', 'extraction_status')

    if 'company_profile' in companies_columns:
        op.drop_column('companies', 'company_profile')






