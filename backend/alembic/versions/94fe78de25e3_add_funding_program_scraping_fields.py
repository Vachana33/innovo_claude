"""add_funding_program_scraping_fields

Revision ID: 94fe78de25e3
Revises: 378640cd9ae5
Create Date: 2026-01-27 11:53:51.382421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94fe78de25e3'
down_revision: Union[str, None] = '378640cd9ae5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('funding_programs')} if 'funding_programs' in inspector.get_table_names() else set()

    # Add description column
    if 'description' not in existing_columns:
        if is_sqlite:
            op.add_column('funding_programs', sa.Column('description', sa.Text(), nullable=True))
        else:
            op.add_column('funding_programs', sa.Column('description', sa.Text(), nullable=True))

    # Add sections_json column
    if 'sections_json' not in existing_columns:
        if is_sqlite:
            op.add_column('funding_programs', sa.Column('sections_json', sa.JSON(), nullable=True))
        else:
            op.add_column('funding_programs', sa.Column('sections_json', sa.JSON(), nullable=True))

    # Add content_hash column
    if 'content_hash' not in existing_columns:
        op.add_column('funding_programs', sa.Column('content_hash', sa.String(), nullable=True))

    # Add last_scraped_at column
    if 'last_scraped_at' not in existing_columns:
        if is_sqlite:
            op.add_column('funding_programs', sa.Column('last_scraped_at', sa.DateTime(timezone=True), nullable=True))
        else:
            op.add_column('funding_programs', sa.Column('last_scraped_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {col['name'] for col in inspector.get_columns('funding_programs')} if 'funding_programs' in inspector.get_table_names() else set()

    if 'last_scraped_at' in existing_columns:
        op.drop_column('funding_programs', 'last_scraped_at')
    if 'content_hash' in existing_columns:
        op.drop_column('funding_programs', 'content_hash')
    if 'sections_json' in existing_columns:
        op.drop_column('funding_programs', 'sections_json')
    if 'description' in existing_columns:
        op.drop_column('funding_programs', 'description')






