"""extend company model

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-01-30 16:00:00.000000

Extend Company model with raw/clean text fields and add CompanyDocument table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add new fields to companies table and create company_documents table.
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    existing_columns = {}
    
    if 'companies' in existing_tables:
        existing_columns = {col['name']: col for col in inspector.get_columns('companies')}
    
    # Add new fields to companies table
    if 'companies' in existing_tables:
        # Add website_raw_text
        if 'website_raw_text' not in existing_columns:
            op.add_column('companies', sa.Column('website_raw_text', sa.Text(), nullable=True))
        
        # Add website_clean_text
        if 'website_clean_text' not in existing_columns:
            op.add_column('companies', sa.Column('website_clean_text', sa.Text(), nullable=True))
        
        # Add transcript_raw
        if 'transcript_raw' not in existing_columns:
            op.add_column('companies', sa.Column('transcript_raw', sa.Text(), nullable=True))
        
        # Add transcript_clean
        if 'transcript_clean' not in existing_columns:
            op.add_column('companies', sa.Column('transcript_clean', sa.Text(), nullable=True))
        
        # Add updated_at
        if 'updated_at' not in existing_columns:
            op.add_column('companies', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    
    # Create company_documents table
    if 'company_documents' not in existing_tables:
        if is_sqlite:
            op.create_table(
                'company_documents',
                sa.Column('id', sa.String(36), primary_key=True, nullable=False),
                sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
                sa.Column('file_id', sa.String(36), sa.ForeignKey('files.id'), nullable=False),
                sa.Column('original_filename', sa.String(), nullable=False),
                sa.Column('display_name', sa.String(), nullable=True),
                sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('uploaded_by', sa.String(), sa.ForeignKey('users.email'), nullable=False),
            )
            # Create indexes separately (SQLite doesn't auto-create from index=True)
            op.create_index('ix_company_documents_company_id', 'company_documents', ['company_id'], unique=False)
            op.create_index('ix_company_documents_file_id', 'company_documents', ['file_id'], unique=False)
        else:
            op.create_table(
                'company_documents',
                sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()'), nullable=False),
                sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
                sa.Column('file_id', UUID(as_uuid=True), sa.ForeignKey('files.id'), nullable=False),
                sa.Column('original_filename', sa.String(), nullable=False),
                sa.Column('display_name', sa.String(), nullable=True),
                sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('uploaded_by', sa.String(), sa.ForeignKey('users.email'), nullable=False),
            )
            # Create indexes - wrap in try-except in case they already exist
            try:
                op.create_index('ix_company_documents_company_id', 'company_documents', ['company_id'], unique=False)
            except Exception:
                pass  # Index might already exist
            try:
                op.create_index('ix_company_documents_file_id', 'company_documents', ['file_id'], unique=False)
            except Exception:
                pass  # Index might already exist
    else:
        # Table exists, check if indexes exist and create if missing
        try:
            existing_indexes = [idx['name'] for idx in inspector.get_indexes('company_documents')]
        except Exception:
            existing_indexes = []
        
        if 'ix_company_documents_company_id' not in existing_indexes:
            try:
                op.create_index('ix_company_documents_company_id', 'company_documents', ['company_id'], unique=False)
            except Exception:
                pass
        if 'ix_company_documents_file_id' not in existing_indexes:
            try:
                op.create_index('ix_company_documents_file_id', 'company_documents', ['file_id'], unique=False)
            except Exception:
                pass


def downgrade() -> None:
    """
    Remove new fields from companies table and drop company_documents table.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # Drop company_documents table
    if 'company_documents' in existing_tables:
        op.drop_index('ix_company_documents_file_id', table_name='company_documents')
        op.drop_index('ix_company_documents_company_id', table_name='company_documents')
        op.drop_table('company_documents')
    
    # Remove columns from companies table
    if 'companies' in existing_tables:
        existing_columns = {col['name']: col for col in inspector.get_columns('companies')}
        
        if 'updated_at' in existing_columns:
            op.drop_column('companies', 'updated_at')
        if 'transcript_clean' in existing_columns:
            op.drop_column('companies', 'transcript_clean')
        if 'transcript_raw' in existing_columns:
            op.drop_column('companies', 'transcript_raw')
        if 'website_clean_text' in existing_columns:
            op.drop_column('companies', 'website_clean_text')
        if 'website_raw_text' in existing_columns:
            op.drop_column('companies', 'website_raw_text')
