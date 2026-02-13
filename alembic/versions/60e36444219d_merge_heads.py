"""merge heads

Revision ID: 60e36444219d
Revises: 8dc621676999, f3b7a99e3b1e
Create Date: 2025-09-24 19:07:31.395149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel



# revision identifiers, used by Alembic.
revision: str = '60e36444219d'
down_revision: Union[str, Sequence[str], None] = ('8dc621676999', 'f3b7a99e3b1e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
