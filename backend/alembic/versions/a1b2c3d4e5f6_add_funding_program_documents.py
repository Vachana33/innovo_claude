"""add_funding_program_documents

Revision ID: a1b2c3d4e5f6
Revises: 94fe78de25e3
Create Date: 2026-01-27 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '94fe78de25e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)

    # Check existing tables
    existing_tables = inspector.get_table_names()

    # 1. Create funding_program_documents table
    if 'funding_program_documents' not in existing_tables:
        if is_sqlite:
            # SQLite doesn't support UUID natively, use String
            op.create_table(
                'funding_program_documents',
                sa.Column('id', sa.String(), nullable=False),
                sa.Column('funding_program_id', sa.Integer(), nullable=False),
                sa.Column('file_id', sa.String(), nullable=False),
                sa.Column('category', sa.String(), nullable=False),
                sa.Column('original_filename', sa.String(), nullable=False),
                sa.Column('display_name', sa.String(), nullable=True),
                sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
                sa.Column('uploaded_by', sa.String(), nullable=False),
                sa.ForeignKeyConstraint(['funding_program_id'], ['funding_programs.id'], ),
                sa.ForeignKeyConstraint(['file_id'], ['files.id'], ),
                sa.ForeignKeyConstraint(['uploaded_by'], ['users.email'], ),
                sa.PrimaryKeyConstraint('id')
            )
        else:
            # PostgreSQL supports UUID
            op.create_table(
                'funding_program_documents',
                sa.Column('id', UUID(as_uuid=True), nullable=False),
                sa.Column('funding_program_id', sa.Integer(), nullable=False),
                sa.Column('file_id', UUID(as_uuid=True), nullable=False),
                sa.Column('category', sa.String(), nullable=False),
                sa.Column('original_filename', sa.String(), nullable=False),
                sa.Column('display_name', sa.String(), nullable=True),
                sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
                sa.Column('uploaded_by', sa.String(), nullable=False),
                sa.ForeignKeyConstraint(['funding_program_id'], ['funding_programs.id'], ),
                sa.ForeignKeyConstraint(['file_id'], ['files.id'], ),
                sa.ForeignKeyConstraint(['uploaded_by'], ['users.email'], ),
                sa.PrimaryKeyConstraint('id')
            )

        # Create indexes
        op.create_index('ix_funding_program_documents_id', 'funding_program_documents', ['id'])
        op.create_index('ix_funding_program_documents_funding_program_id', 'funding_program_documents', ['funding_program_id'])
        op.create_index('ix_funding_program_documents_file_id', 'funding_program_documents', ['file_id'])
        op.create_index('ix_funding_program_documents_program_category', 'funding_program_documents', ['funding_program_id', 'category'])

    # 2. Add guidelines_text to funding_programs table
    existing_columns = {col['name'] for col in inspector.get_columns('funding_programs')} if 'funding_programs' in existing_tables else set()

    if 'guidelines_text' not in existing_columns:
        op.add_column('funding_programs', sa.Column('guidelines_text', sa.Text(), nullable=True))

    # 3. Add guidelines_text_file_id to funding_programs table
    if 'guidelines_text_file_id' not in existing_columns:
        if is_sqlite:
            op.add_column('funding_programs', sa.Column('guidelines_text_file_id', sa.String(), nullable=True))
        else:
            op.add_column('funding_programs', sa.Column('guidelines_text_file_id', UUID(as_uuid=True), nullable=True))

        # Add foreign key constraint (only for PostgreSQL, SQLite doesn't support adding FK after table creation easily)
        if not is_sqlite:
            op.create_foreign_key(
                'fk_funding_programs_guidelines_text_file_id',
                'funding_programs',
                'files',
                ['guidelines_text_file_id'],
                ['id']
            )


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Remove columns from funding_programs
    if 'funding_programs' in existing_tables:
        existing_columns = {col['name'] for col in inspector.get_columns('funding_programs')}

        if 'guidelines_text_file_id' in existing_columns:
            if not is_sqlite:
                # Drop foreign key constraint first (PostgreSQL)
                try:
                    op.drop_constraint('fk_funding_programs_guidelines_text_file_id', 'funding_programs', type_='foreignkey')
                except:
                    pass
            op.drop_column('funding_programs', 'guidelines_text_file_id')

        if 'guidelines_text' in existing_columns:
            op.drop_column('funding_programs', 'guidelines_text')

    # Drop funding_program_documents table
    if 'funding_program_documents' in existing_tables:
        op.drop_index('ix_funding_program_documents_program_category', table_name='funding_program_documents')
        op.drop_index('ix_funding_program_documents_file_id', table_name='funding_program_documents')
        op.drop_index('ix_funding_program_documents_funding_program_id', table_name='funding_program_documents')
        op.drop_index('ix_funding_program_documents_id', table_name='funding_program_documents')
        op.drop_table('funding_program_documents')
