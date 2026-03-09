"""add_template_fields_to_documents

Revision ID: f6g7h8i9j0k1
Revises: e2f3a4b5c6d7
Create Date: 2026-01-30 18:00:00.000000

Add template_id and template_name fields to documents table.
Templates now belong to documents, not funding programs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'f6g7h8i9j0k1'
down_revision: Union[str, None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add template_id and template_name columns to documents table.
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_columns = [col['name'] for col in inspector.get_columns('documents')]
    
    # Add template_id (UUID FK to user_templates)
    if 'template_id' not in existing_columns:
        if is_sqlite:
            op.add_column('documents', sa.Column('template_id', sa.String(36), nullable=True))
        else:
            op.add_column('documents', sa.Column('template_id', UUID(as_uuid=True), nullable=True))
            op.create_foreign_key(
                'fk_documents_template_id',
                'documents',
                'user_templates',
                ['template_id'],
                ['id']
            )
        op.create_index('ix_documents_template_id', 'documents', ['template_id'], unique=False)
    
    # Add template_name (String for system templates)
    if 'template_name' not in existing_columns:
        op.add_column('documents', sa.Column('template_name', sa.String(), nullable=True))
        op.create_index('ix_documents_template_name', 'documents', ['template_name'], unique=False)


def downgrade() -> None:
    """
    Remove template_id and template_name columns from documents table.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = [col['name'] for col in inspector.get_columns('documents')]
    
    if 'template_name' in existing_columns:
        op.drop_index('ix_documents_template_name', table_name='documents')
        op.drop_column('documents', 'template_name')
    
    if 'template_id' in existing_columns:
        bind = op.get_bind()
        is_sqlite = bind.dialect.name == 'sqlite'
        if not is_sqlite:
            op.drop_constraint('fk_documents_template_id', 'documents', type_='foreignkey')
        op.drop_index('ix_documents_template_id', table_name='documents')
        op.drop_column('documents', 'template_id')
