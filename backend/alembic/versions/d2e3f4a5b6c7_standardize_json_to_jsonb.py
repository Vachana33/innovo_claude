"""Standardize JSON columns to JSONB (Group A: json -> jsonb)

Revision ID: d2e3f4a5b6c7
Revises: a2c163c6a76c
Create Date: 2026-03-23

Converts all sa.JSON columns in the public schema to JSONB.
PostgreSQL can cast json -> jsonb natively with zero data loss.

Columns converted:
  companies.company_profile
  documents.content_json
  documents.chat_history
  user_templates.template_structure
  funding_program_guidelines_summary.rules_json
  alte_vorhabensbeschreibung_style_profile.style_summary_json
  project_contexts.assembly_progress_json
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'a2c163c6a76c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'companies', 'company_profile',
        existing_type=sa.JSON(),
        type_=JSONB(),
        postgresql_using='company_profile::jsonb',
        existing_nullable=True,
    )

    op.alter_column(
        'documents', 'content_json',
        existing_type=sa.JSON(),
        type_=JSONB(),
        postgresql_using='content_json::jsonb',
        existing_nullable=False,
    )

    op.alter_column(
        'documents', 'chat_history',
        existing_type=sa.JSON(),
        type_=JSONB(),
        postgresql_using='chat_history::jsonb',
        existing_nullable=True,
    )

    op.alter_column(
        'user_templates', 'template_structure',
        existing_type=sa.JSON(),
        type_=JSONB(),
        postgresql_using='template_structure::jsonb',
        existing_nullable=False,
    )

    op.alter_column(
        'funding_program_guidelines_summary', 'rules_json',
        existing_type=sa.JSON(),
        type_=JSONB(),
        postgresql_using='rules_json::jsonb',
        existing_nullable=False,
    )

    op.alter_column(
        'alte_vorhabensbeschreibung_style_profile', 'style_summary_json',
        existing_type=sa.JSON(),
        type_=JSONB(),
        postgresql_using='style_summary_json::jsonb',
        existing_nullable=False,
    )

    op.alter_column(
        'project_contexts', 'assembly_progress_json',
        existing_type=sa.JSON(),
        type_=JSONB(),
        postgresql_using='assembly_progress_json::jsonb',
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'project_contexts', 'assembly_progress_json',
        existing_type=JSONB(),
        type_=sa.JSON(),
        postgresql_using='assembly_progress_json::json',
        existing_nullable=True,
    )

    op.alter_column(
        'alte_vorhabensbeschreibung_style_profile', 'style_summary_json',
        existing_type=JSONB(),
        type_=sa.JSON(),
        postgresql_using='style_summary_json::json',
        existing_nullable=False,
    )

    op.alter_column(
        'funding_program_guidelines_summary', 'rules_json',
        existing_type=JSONB(),
        type_=sa.JSON(),
        postgresql_using='rules_json::json',
        existing_nullable=False,
    )

    op.alter_column(
        'user_templates', 'template_structure',
        existing_type=JSONB(),
        type_=sa.JSON(),
        postgresql_using='template_structure::json',
        existing_nullable=False,
    )

    op.alter_column(
        'documents', 'chat_history',
        existing_type=JSONB(),
        type_=sa.JSON(),
        postgresql_using='chat_history::json',
        existing_nullable=True,
    )

    op.alter_column(
        'documents', 'content_json',
        existing_type=JSONB(),
        type_=sa.JSON(),
        postgresql_using='content_json::json',
        existing_nullable=False,
    )

    op.alter_column(
        'companies', 'company_profile',
        existing_type=JSONB(),
        type_=sa.JSON(),
        postgresql_using='company_profile::json',
        existing_nullable=True,
    )
