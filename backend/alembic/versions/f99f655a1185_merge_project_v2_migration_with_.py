"""merge project v2 migration with document migration

Revision ID: f99f655a1185
Revises: a2b3c4d5e6f7, a3b4c5d6e7f8
Create Date: 2026-03-12 12:39:57.916235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f99f655a1185'
down_revision: Union[str, None] = ('a2b3c4d5e6f7', 'a3b4c5d6e7f8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass






