"""Convert TEXT JSON columns in project_contexts and projects to JSONB (Group B)

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-03-23

Converts TEXT columns that store serialised JSON strings to JSONB.
PostgreSQL will raise an error (and roll back the whole migration) if any
non-null row contains invalid JSON — this is the desired behaviour.

Run the preflight SQL below in Supabase before applying this migration:

  SELECT id, template_overrides_json
  FROM projects
  WHERE template_overrides_json IS NOT NULL
    AND template_overrides_json !~ '^\\s*[\\{\\[]';

If that query returns any rows, fix or NULL those values before proceeding.

Columns converted:
  project_contexts.company_profile_json   TEXT -> JSONB
  project_contexts.funding_rules_json     TEXT -> JSONB
  project_contexts.domain_research_json   TEXT -> JSONB
  project_contexts.retrieved_examples_json TEXT -> JSONB
  project_contexts.style_profile_json     TEXT -> JSONB
  projects.template_overrides_json        TEXT -> JSONB
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The ::jsonb cast validates JSON on the fly.
    # Any row with invalid JSON causes a PostgreSQL error and rolls back entirely.

    op.alter_column(
        'project_contexts', 'company_profile_json',
        existing_type=sa.Text(),
        type_=JSONB(),
        postgresql_using='company_profile_json::jsonb',
        existing_nullable=True,
    )

    op.alter_column(
        'project_contexts', 'funding_rules_json',
        existing_type=sa.Text(),
        type_=JSONB(),
        postgresql_using='funding_rules_json::jsonb',
        existing_nullable=True,
    )

    op.alter_column(
        'project_contexts', 'domain_research_json',
        existing_type=sa.Text(),
        type_=JSONB(),
        postgresql_using='domain_research_json::jsonb',
        existing_nullable=True,
    )

    op.alter_column(
        'project_contexts', 'retrieved_examples_json',
        existing_type=sa.Text(),
        type_=JSONB(),
        postgresql_using='retrieved_examples_json::jsonb',
        existing_nullable=True,
    )

    op.alter_column(
        'project_contexts', 'style_profile_json',
        existing_type=sa.Text(),
        type_=JSONB(),
        postgresql_using='style_profile_json::jsonb',
        existing_nullable=True,
    )

    op.alter_column(
        'projects', 'template_overrides_json',
        existing_type=sa.Text(),
        type_=JSONB(),
        postgresql_using='template_overrides_json::jsonb',
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'projects', 'template_overrides_json',
        existing_type=JSONB(),
        type_=sa.Text(),
        postgresql_using='template_overrides_json::text',
        existing_nullable=True,
    )

    op.alter_column(
        'project_contexts', 'style_profile_json',
        existing_type=JSONB(),
        type_=sa.Text(),
        postgresql_using='style_profile_json::text',
        existing_nullable=True,
    )

    op.alter_column(
        'project_contexts', 'retrieved_examples_json',
        existing_type=JSONB(),
        type_=sa.Text(),
        postgresql_using='retrieved_examples_json::text',
        existing_nullable=True,
    )

    op.alter_column(
        'project_contexts', 'domain_research_json',
        existing_type=JSONB(),
        type_=sa.Text(),
        postgresql_using='domain_research_json::text',
        existing_nullable=True,
    )

    op.alter_column(
        'project_contexts', 'funding_rules_json',
        existing_type=JSONB(),
        type_=sa.Text(),
        postgresql_using='funding_rules_json::text',
        existing_nullable=True,
    )

    op.alter_column(
        'project_contexts', 'company_profile_json',
        existing_type=JSONB(),
        type_=sa.Text(),
        postgresql_using='company_profile_json::text',
        existing_nullable=True,
    )
