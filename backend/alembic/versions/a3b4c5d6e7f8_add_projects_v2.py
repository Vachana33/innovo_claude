"""add_projects_v2

Revision ID: a3b4c5d6e7f8
Revises: 8a8eb899811f
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, None] = '8a8eb899811f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- projects table ---
    op.create_table(
    'projects',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_email', sa.String(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=True),
    sa.Column('funding_program_id', sa.Integer(), nullable=True),
    sa.Column('topic', sa.Text(), nullable=False),
    sa.Column('status', sa.String(), nullable=False, server_default=sa.text("'pending'")),
    sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),

    sa.ForeignKeyConstraint(['user_email'], ['users.email'], name='fk_projects_user_email'),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name='fk_projects_company_id', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['funding_program_id'], ['funding_programs.id'], name='fk_projects_funding_program_id', ondelete='SET NULL'),

    sa.PrimaryKeyConstraint('id')
)
    op.create_index('ix_projects_user_email', 'projects', ['user_email'])
    op.create_index('ix_projects_company_id', 'projects', ['company_id'])
    op.create_index('ix_projects_funding_program_id', 'projects', ['funding_program_id'])
    op.create_index('ix_projects_created_at', 'projects', ['created_at'])

    # --- project_contexts table ---
    op.create_table(
        'project_contexts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('company_profile_json', sa.Text(), nullable=True),
        sa.Column('funding_rules_json', sa.Text(), nullable=True),
        sa.Column('domain_research_json', sa.Text(), nullable=True),
        sa.Column('retrieved_examples_json', sa.Text(), nullable=True),
        sa.Column('style_profile_json', sa.Text(), nullable=True),
        sa.Column('website_text_preview', sa.Text(), nullable=True),
        sa.Column('context_hash', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_project_contexts_project_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_project_contexts_project_id'),
    )

    # --- documents.project_id column ---
    op.add_column('documents', sa.Column('project_id', sa.String(), nullable=True))
    op.create_foreign_key(
        'fk_documents_project_id',
        'documents', 'projects',
        ['project_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_documents_project_id', 'documents', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_documents_project_id', table_name='documents')
    op.drop_constraint('fk_documents_project_id', 'documents', type_='foreignkey')
    op.drop_column('documents', 'project_id')

    op.drop_table('project_contexts')

    op.drop_index('ix_projects_created_at', table_name='projects')
    op.drop_index('ix_projects_funding_program_id', table_name='projects')
    op.drop_index('ix_projects_company_id', table_name='projects')
    op.drop_index('ix_projects_user_email', table_name='projects')
    op.drop_table('projects')
