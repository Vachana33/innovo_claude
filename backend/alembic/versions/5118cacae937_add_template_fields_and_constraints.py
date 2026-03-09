"""add_template_fields_and_constraints

Revision ID: 5118cacae937
Revises: 0fb7cad86248
Create Date: 2026-01-20 15:12:53.217203

Adds template_name to funding_programs and funding_program_id to documents.
Includes UNIQUE constraint on (company_id, funding_program_id, type) to prevent duplicates.
All fields are nullable for backward compatibility with legacy documents.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5118cacae937'
down_revision: Union[str, None] = '0fb7cad86248'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if we're using SQLite (requires batch mode)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    # Check existing columns to avoid duplicates
    from sqlalchemy import inspect
    inspector = inspect(bind)

    funding_programs_columns = [col['name'] for col in inspector.get_columns('funding_programs')]
    documents_columns = [col['name'] for col in inspector.get_columns('documents')]

    # Add template_name to funding_programs (if not exists)
    if 'template_name' not in funding_programs_columns:
        op.add_column('funding_programs', sa.Column('template_name', sa.String(), nullable=True))

    # Add funding_program_id to documents (nullable for legacy documents) (if not exists)
    if 'funding_program_id' not in documents_columns:
        op.add_column('documents', sa.Column('funding_program_id', sa.Integer(), nullable=True))

    if is_sqlite:
        # SQLite: Use batch mode for constraints
        with op.batch_alter_table('documents', schema=None) as batch_op:
            # Create index for performance
            batch_op.create_index('ix_documents_funding_program_id', ['funding_program_id'])

            # Add UNIQUE constraint (PostgreSQL allows multiple NULLs, so legacy docs won't conflict)
            # Note: SQLite doesn't support foreign keys in batch mode easily, so we skip it
            # The foreign key relationship is enforced at the application level
            batch_op.create_unique_constraint(
                'uq_document_company_program_type',
                ['company_id', 'funding_program_id', 'type']
            )
    else:
        # PostgreSQL: Use standard operations
        # Create foreign key
        op.create_foreign_key(
            'fk_documents_funding_program',
            'documents',
            'funding_programs',
            ['funding_program_id'],
            ['id']
        )

        # Create index for performance
        op.create_index('ix_documents_funding_program_id', 'documents', ['funding_program_id'])

        # Add UNIQUE constraint (PostgreSQL allows multiple NULLs, so legacy docs won't conflict)
        op.create_unique_constraint(
            'uq_document_company_program_type',
            'documents',
            ['company_id', 'funding_program_id', 'type']
        )


def downgrade() -> None:
    # Check if we're using SQLite (requires batch mode)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    if is_sqlite:
        # SQLite: Use batch mode for constraints
        with op.batch_alter_table('documents', schema=None) as batch_op:
            # Remove UNIQUE constraint
            batch_op.drop_constraint('uq_document_company_program_type', type_='unique')
            # Remove index
            batch_op.drop_index('ix_documents_funding_program_id')
    else:
        # PostgreSQL: Use standard operations
        # Remove UNIQUE constraint
        op.drop_constraint('uq_document_company_program_type', 'documents', type_='unique')
        # Remove index
        op.drop_index('ix_documents_funding_program_id', table_name='documents')
        # Remove foreign key
        op.drop_constraint('fk_documents_funding_program', 'documents', type_='foreignkey')

    # Remove columns
    op.drop_column('documents', 'funding_program_id')
    op.drop_column('funding_programs', 'template_name')






