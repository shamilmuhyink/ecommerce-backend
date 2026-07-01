"""add_outbox_events_table

Revision ID: c3d4e5f6a7b8
Revises: 4e7675e29d26
Create Date: 2026-06-30 11:45:02.793967

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = '4e7675e29d26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
