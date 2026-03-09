"""remove_funding_program_scraping_fields

Revision ID: b7c8d9e0f1a2
Revises: 8a8eb899811f
Create Date: 2026-01-30 12:00:00.000000

Remove scraping-related fields from funding_programs table:
- description (scraped description)
- sections_json (scraped sections)
- content_hash (hash of scraped content)
- last_scraped_at (last scrape timestamp)
- guidelines_text (text content from guidelines files)
- guidelines_text_file_id (reference to file)

These fields are no longer used after refactoring to use funding_program_documents.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = '8a8eb899811f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove scraping-related columns from funding_programs table.
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'funding_programs' not in existing_tables:
        # Table doesn't exist, nothing to do
        return

    existing_columns = {col['name'] for col in inspector.get_columns('funding_programs')}

    # Drop foreign key constraint for guidelines_text_file_id first (PostgreSQL only)
    if 'guidelines_text_file_id' in existing_columns and not is_sqlite:
        try:
            op.drop_constraint(
                'fk_funding_programs_guidelines_text_file_id',
                'funding_programs',
                type_='foreignkey'
            )
        except Exception:
            # Constraint might not exist, ignore
            pass

    # Drop columns in reverse order of dependencies
    # Drop guidelines_text_file_id first (has FK constraint)
    if 'guidelines_text_file_id' in existing_columns:
        op.drop_column('funding_programs', 'guidelines_text_file_id')

    # Drop guidelines_text
    if 'guidelines_text' in existing_columns:
        op.drop_column('funding_programs', 'guidelines_text')

    # Drop scraping fields
    if 'last_scraped_at' in existing_columns:
        op.drop_column('funding_programs', 'last_scraped_at')

    if 'content_hash' in existing_columns:
        op.drop_column('funding_programs', 'content_hash')

    if 'sections_json' in existing_columns:
        op.drop_column('funding_programs', 'sections_json')

    if 'description' in existing_columns:
        op.drop_column('funding_programs', 'description')


def downgrade() -> None:
    """
    Recreate scraping-related columns in funding_programs table.
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'funding_programs' not in existing_tables:
        # Table doesn't exist, nothing to do
        return

    existing_columns = {col['name'] for col in inspector.get_columns('funding_programs')}

    # Recreate description column
    if 'description' not in existing_columns:
        op.add_column('funding_programs', sa.Column('description', sa.Text(), nullable=True))

    # Recreate sections_json column
    if 'sections_json' not in existing_columns:
        op.add_column('funding_programs', sa.Column('sections_json', sa.JSON(), nullable=True))

    # Recreate content_hash column
    if 'content_hash' not in existing_columns:
        op.add_column('funding_programs', sa.Column('content_hash', sa.String(), nullable=True))

    # Recreate last_scraped_at column
    if 'last_scraped_at' not in existing_columns:
        op.add_column('funding_programs', sa.Column('last_scraped_at', sa.DateTime(timezone=True), nullable=True))

    # Recreate guidelines_text column
    if 'guidelines_text' not in existing_columns:
        op.add_column('funding_programs', sa.Column('guidelines_text', sa.Text(), nullable=True))

    # Recreate guidelines_text_file_id column
    if 'guidelines_text_file_id' not in existing_columns:
        if is_sqlite:
            op.add_column('funding_programs', sa.Column('guidelines_text_file_id', sa.String(), nullable=True))
        else:
            op.add_column('funding_programs', sa.Column('guidelines_text_file_id', UUID(as_uuid=True), nullable=True))

            # Recreate foreign key constraint for PostgreSQL
            try:
                op.create_foreign_key(
                    'fk_funding_programs_guidelines_text_file_id',
                    'funding_programs',
                    'files',
                    ['guidelines_text_file_id'],
                    ['id']
                )
            except Exception:
                # Constraint might already exist, ignore
                pass
