"""phase2_context_assembler_schema

Revision ID: b1c2d3e4f5a6
Revises: f99f655a1185
Create Date: 2026-03-16 00:00:00.000000

Adds Phase 2 columns:
  - projects.company_name
  - projects.template_overrides_json
  - project_contexts.completeness_score
  - project_contexts.company_discovery_status
  - project_contexts.assembly_progress_json
  - users.is_admin
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'f99f655a1185'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- projects ---
    op.add_column('projects', sa.Column('company_name', sa.Text(), nullable=True))
    op.add_column('projects', sa.Column('template_overrides_json', sa.Text(), nullable=True))

    # --- project_contexts ---
    op.add_column('project_contexts', sa.Column('completeness_score', sa.Integer(), nullable=True))
    op.add_column('project_contexts', sa.Column('company_discovery_status', sa.String(), nullable=True))
    # Use JSON on SQLite, JSONB on PostgreSQL – Alembic renders the correct DDL per dialect
    op.add_column('project_contexts', sa.Column('assembly_progress_json', sa.JSON(), nullable=True))

    # --- users ---
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    op.drop_column('users', 'is_admin')
    op.drop_column('project_contexts', 'assembly_progress_json')
    op.drop_column('project_contexts', 'company_discovery_status')
    op.drop_column('project_contexts', 'completeness_score')
    op.drop_column('projects', 'template_overrides_json')
    op.drop_column('projects', 'company_name')
