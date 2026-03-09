"""add_phase_2_5_template_system

Revision ID: 55cd193493bc
Revises: add_processing_cache_tables
Create Date: 2026-01-26 13:07:30.627342

Phase 2.5: Template System
- Adds template_source and template_ref to funding_programs (replaces template_name)
- Creates user_templates table for user-defined templates
- Keeps template_name for backward compatibility
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '55cd193493bc'
down_revision: Union[str, None] = 'add_processing_cache_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Phase 2.5: Add template system support.

    1. Add template_source and template_ref columns to funding_programs
    2. Create user_templates table for user-defined templates
    3. Keep template_name for backward compatibility (no migration needed)
    """
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('funding_programs')} if 'funding_programs' in inspector.get_table_names() else set()
    existing_tables = inspector.get_table_names()

    # 1. Add template_source and template_ref to funding_programs
    if 'template_source' not in existing_columns:
        op.add_column('funding_programs', sa.Column('template_source', sa.String(), nullable=True))
        op.create_index('ix_funding_programs_template_source', 'funding_programs', ['template_source'])

    if 'template_ref' not in existing_columns:
        op.add_column('funding_programs', sa.Column('template_ref', sa.String(), nullable=True))
        op.create_index('ix_funding_programs_template_ref', 'funding_programs', ['template_ref'])

    # 2. Create user_templates table
    if 'user_templates' not in existing_tables:
        if is_sqlite:
            # SQLite: Use String(36) for UUID
            op.create_table(
                'user_templates',
                sa.Column('id', sa.String(36), primary_key=True, nullable=False),
                sa.Column('name', sa.String(), nullable=False),
                sa.Column('description', sa.Text(), nullable=True),
                sa.Column('template_structure', sa.JSON(), nullable=False),
                sa.Column('user_email', sa.String(), sa.ForeignKey('users.email'), nullable=False),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            )
            op.create_index('ix_user_templates_user_email', 'user_templates', ['user_email'])
            op.create_index('ix_user_templates_id', 'user_templates', ['id'])
        else:
            # PostgreSQL: Use UUID type
            op.create_table(
                'user_templates',
                sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
                sa.Column('name', sa.String(), nullable=False),
                sa.Column('description', sa.Text(), nullable=True),
                sa.Column('template_structure', postgresql.JSON(), nullable=False),
                sa.Column('user_email', sa.String(), sa.ForeignKey('users.email'), nullable=False),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            )
            op.create_index('ix_user_templates_user_email', 'user_templates', ['user_email'])
            op.create_index('ix_user_templates_id', 'user_templates', ['id'])


def downgrade() -> None:
    """
    Remove Phase 2.5 template system changes.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    existing_columns = {col['name'] for col in inspector.get_columns('funding_programs')} if 'funding_programs' in existing_tables else set()

    # Drop user_templates table
    if 'user_templates' in existing_tables:
        op.drop_index('ix_user_templates_id', table_name='user_templates')
        op.drop_index('ix_user_templates_user_email', table_name='user_templates')
        op.drop_table('user_templates')

    # Remove template_source and template_ref columns
    if 'template_ref' in existing_columns:
        op.drop_index('ix_funding_programs_template_ref', table_name='funding_programs')
        op.drop_column('funding_programs', 'template_ref')
    
    if 'template_source' in existing_columns:
        op.drop_index('ix_funding_programs_template_source', table_name='funding_programs')
        op.drop_column('funding_programs', 'template_source')
