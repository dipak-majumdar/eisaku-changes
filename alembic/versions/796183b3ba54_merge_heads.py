"""merge heads

Revision ID: 796183b3ba54
Revises: 772392c1b3a2, 86c35fa1acb3
Create Date: 2026-02-12 15:27:58.259210

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel



# revision identifiers, used by Alembic.
revision: str = '796183b3ba54'
down_revision: Union[str, Sequence[str], None] = ('772392c1b3a2', '86c35fa1acb3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
