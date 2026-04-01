"""merge phase2 heads

Revision ID: a2c163c6a76c
Revises: b1c2d3e4f5a6, c1d2e3f4a5b6
Create Date: 2026-03-23 11:29:15.184726

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2c163c6a76c'
down_revision: Union[str, None] = ('b1c2d3e4f5a6', 'c1d2e3f4a5b6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass






