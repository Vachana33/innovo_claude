"""allow_multiple_docs_per_company_program

Revision ID: a2b3c4d5e6f7
Revises: f6g7h8i9j0k1
Create Date: 2026-02-24 12:00:00.000000

Allow multiple documents per (company_id, funding_program_id, type).
- Drop unique constraint uq_document_company_program_type
- Add nullable title column to documents for distinguishing documents in the list
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f6g7h8i9j0k1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    inspector = sa.inspect(bind)

    # Drop unique constraint uq_document_company_program_type
    if "documents" in inspector.get_table_names():
        existing_constraints = [c["name"] for c in inspector.get_unique_constraints("documents")]
        if "uq_document_company_program_type" in existing_constraints:
            if is_sqlite:
                with op.batch_alter_table("documents", schema=None) as batch_op:
                    batch_op.drop_constraint("uq_document_company_program_type", type_="unique")
            else:
                op.drop_constraint(
                    "uq_document_company_program_type",
                    "documents",
                    type_="unique",
                )

    # Add nullable title column
    documents_columns = [col["name"] for col in inspector.get_columns("documents")]
    if "title" not in documents_columns:
        op.add_column(
            "documents",
            sa.Column("title", sa.String(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    inspector = sa.inspect(bind)
    documents_columns = [col["name"] for col in inspector.get_columns("documents")]

    # Remove title column
    if "title" in documents_columns:
        op.drop_column("documents", "title")

    # Re-create unique constraint (will fail if multiple rows exist per company_id+funding_program_id+type)
    if is_sqlite:
        with op.batch_alter_table("documents", schema=None) as batch_op:
            batch_op.create_unique_constraint(
                "uq_document_company_program_type",
                ["company_id", "funding_program_id", "type"],
            )
    else:
        op.create_unique_constraint(
            "uq_document_company_program_type",
            "documents",
            ["company_id", "funding_program_id", "type"],
        )
