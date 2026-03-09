"""add_missing_guidelines_columns

Revision ID: 8a8eb899811f
Revises: a1b2c3d4e5f6
Create Date: 2026-01-29 13:21:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '8a8eb899811f'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'funding_programs' in existing_tables:
        existing_columns = {col['name'] for col in inspector.get_columns('funding_programs')}

        # Add guidelines_text column if it doesn't exist
        if 'guidelines_text' not in existing_columns:
            op.add_column('funding_programs', sa.Column('guidelines_text', sa.Text(), nullable=True))

        # Add guidelines_text_file_id column if it doesn't exist
        if 'guidelines_text_file_id' not in existing_columns:
            if is_sqlite:
                op.add_column('funding_programs', sa.Column('guidelines_text_file_id', sa.String(), nullable=True))
            else:
                op.add_column('funding_programs', sa.Column('guidelines_text_file_id', UUID(as_uuid=True), nullable=True))

                # Add foreign key constraint for PostgreSQL
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


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'funding_programs' in existing_tables:
        existing_columns = {col['name'] for col in inspector.get_columns('funding_programs')}

        if 'guidelines_text_file_id' in existing_columns:
            if not is_sqlite:
                # Drop foreign key constraint first (PostgreSQL)
                try:
                    op.drop_constraint('fk_funding_programs_guidelines_text_file_id', 'funding_programs', type_='foreignkey')
                except Exception:
                    pass
            op.drop_column('funding_programs', 'guidelines_text_file_id')
        
        if 'guidelines_text' in existing_columns:
            op.drop_column('funding_programs', 'guidelines_text')