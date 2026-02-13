"""add_status_note_field_and_change_enum_to_closed

Revision ID: 4f351295f28
Revises: c88967d0598b
Create Date: 2025-10-28 15:31:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '4f351295f28'
down_revision: Union[str, Sequence[str], None] = 'c88967d0598b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Add status_note field (if not exists)
    2. Change ENUM from old values to new values
    3. Update existing data
    """
    
    # ✅ Get connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # ✅ Step 1: Add status_note field ONLY if it doesn't exist
    columns = [col['name'] for col in inspector.get_columns('marketline_complaints')]
    if 'status_note' not in columns:
        op.add_column(
            'marketline_complaints',
            sa.Column('status_note', sa.String(length=1000), nullable=True)
        )
    
    # ✅ Step 2: Get current ENUM values
    result = conn.execute(sa.text("""
        SELECT COLUMN_TYPE 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'marketline_complaints' 
        AND COLUMN_NAME = 'status'
    """))
    current_enum = result.scalar()
    
    # ✅ Step 3: Only update ENUM if it still has old values
    if 'Resolved' in current_enum or 'In Progress' in current_enum:
        # Expand ENUM to include both old and new values temporarily
        op.execute("""
            ALTER TABLE marketline_complaints
            MODIFY status ENUM('OPEN', 'In Progress', 'Resolved', 'IN PROGRESS', 'CLOSED') DEFAULT 'OPEN'
        """)
        
        # Update existing 'In Progress' to 'IN PROGRESS'
        op.execute("""
            UPDATE marketline_complaints
            SET status = 'IN PROGRESS'
            WHERE status = 'In Progress'
        """)
        
        # Update existing 'Resolved' to 'CLOSED'
        op.execute("""
            UPDATE marketline_complaints
            SET status = 'CLOSED'
            WHERE status = 'Resolved'
        """)
        
        # Update status history table (if exists)
        tables = inspector.get_table_names()
        if 'marketline_complaint_status_history' in tables:
            op.execute("""
                UPDATE marketline_complaint_status_history
                SET status = 'IN PROGRESS'
                WHERE status = 'In Progress'
            """)
            
            op.execute("""
                UPDATE marketline_complaint_status_history
                SET status = 'CLOSED'
                WHERE status = 'Resolved'
            """)
        
        # Remove old values from ENUM (keep only new values)
        op.execute("""
            ALTER TABLE marketline_complaints
            MODIFY status ENUM('OPEN', 'IN PROGRESS', 'CLOSED') DEFAULT 'OPEN'
        """)


def downgrade() -> None:
    """Reverse the changes"""
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Expand ENUM to include both old and new values
    op.execute("""
        ALTER TABLE marketline_complaints
        MODIFY status ENUM('OPEN', 'In Progress', 'Resolved', 'IN PROGRESS', 'CLOSED') DEFAULT 'OPEN'
    """)
    
    # Update 'IN PROGRESS' back to 'In Progress'
    op.execute("""
        UPDATE marketline_complaints
        SET status = 'In Progress'
        WHERE status = 'IN PROGRESS'
    """)
    
    # Update 'CLOSED' back to 'Resolved'
    op.execute("""
        UPDATE marketline_complaints
        SET status = 'Resolved'
        WHERE status = 'CLOSED'
    """)
    
    # Update status history back (if exists)
    tables = inspector.get_table_names()
    if 'marketline_complaint_status_history' in tables:
        op.execute("""
            UPDATE marketline_complaint_status_history
            SET status = 'In Progress'
            WHERE status = 'IN PROGRESS'
        """)
        
        op.execute("""
            UPDATE marketline_complaint_status_history
            SET status = 'Resolved'
            WHERE status = 'CLOSED'
        """)
    
    # Remove new values from ENUM (restore old values)
    op.execute("""
        ALTER TABLE marketline_complaints
        MODIFY status ENUM('OPEN', 'In Progress', 'Resolved') DEFAULT 'OPEN'
    """)
    
    # Drop status_note field if it exists
    columns = [col['name'] for col in inspector.get_columns('marketline_complaints')]
    if 'status_note' in columns:
        op.drop_column('marketline_complaints', 'status_note')
