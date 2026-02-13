"""merge multiple heads

Revision ID: a35751a61809
Revises: bc44e7939eca, bc637c22b41f
Create Date: 2025-12-03 17:31:59.351448

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel



# revision identifiers, used by Alembic.
revision: str = 'a35751a61809'
down_revision: Union[str, Sequence[str], None] = ('bc44e7939eca', 'bc637c22b41f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
