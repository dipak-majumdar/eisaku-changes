"""Merge all heads

Revision ID: 979abb04ea66
Revises: 28f9f36e8015, 61208a83eaa7
Create Date: 2025-11-20 16:51:58.051036

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel



# revision identifiers, used by Alembic.
revision: str = '979abb04ea66'
down_revision: Union[str, Sequence[str], None] = ('28f9f36e8015', '61208a83eaa7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
