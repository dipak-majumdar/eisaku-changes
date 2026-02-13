"""change enums

Revision ID: 5987872686bc
Revises: cf278b70c4f7
Create Date: 2025-10-27 15:09:00.117977

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '5987872686bc'
down_revision: Union[str, Sequence[str], None] = 'cf278b70c4f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Safe 3-step ENUM migration."""
    
    # ✅ STEP 1: Expand ENUM to include BOTH old and new values
    op.execute("""
        ALTER TABLE marketline_complaints
        MODIFY status ENUM(
            'PENDING',      -- old values
            'APPROVED',     -- old values
            'REJECTED',     -- old values
            'OPEN',         -- new values
            'INPROGRESS',   -- new values
            'RESOLVED'      -- new values
        ) NOT NULL
    """)
    
    # ✅ STEP 2: Migrate existing data to new values
    # Map old status to new status
    op.execute("""
        UPDATE marketline_complaints
        SET status = CASE
            WHEN status = 'PENDING' THEN 'OPEN'
            WHEN status = 'APPROVED' THEN 'INPROGRESS'
            WHEN status = 'REJECTED' THEN 'RESOLVED'
            ELSE status
        END
    """)
    
    # ✅ STEP 3: Remove old values from ENUM (safe now that data is migrated)
    op.execute("""
        ALTER TABLE marketline_complaints
        MODIFY status ENUM('OPEN', 'INPROGRESS', 'RESOLVED') NOT NULL
    """)


def downgrade() -> None:
    """Downgrade schema - Reverse the migration."""
    
    # STEP 1: Expand ENUM to include both
    op.execute("""
        ALTER TABLE marketline_complaints
        MODIFY status ENUM(
            'OPEN',
            'INPROGRESS',
            'RESOLVED',
            'PENDING',
            'APPROVED',
            'REJECTED'
        ) NOT NULL
    """)
    
    # STEP 2: Migrate data back to old values
    op.execute("""
        UPDATE marketline_complaints
        SET status = CASE
            WHEN status = 'OPEN' THEN 'PENDING'
            WHEN status = 'INPROGRESS' THEN 'APPROVED'
            WHEN status = 'RESOLVED' THEN 'REJECTED'
            ELSE status
        END
    """)
    
    # STEP 3: Remove new values from ENUM
    op.execute("""
        ALTER TABLE marketline_complaints
        MODIFY status ENUM('PENDING', 'APPROVED', 'REJECTED') NOT NULL
    """)
