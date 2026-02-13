"""merge complaint and other changes

Revision ID: 1ade47651d6f
Revises: 4f351295f28, 587021a82156
Create Date: 2025-10-28 16:40:36.830329

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel



# revision identifiers, used by Alembic.
revision: str = '1ade47651d6f'
down_revision: Union[str, Sequence[str], None] = ('4f351295f28', '587021a82156')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
