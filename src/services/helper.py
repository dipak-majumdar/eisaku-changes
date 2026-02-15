from uuid import UUID
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from models import Employee
from models.user import User


async def get_supervisors_in_branch(session: AsyncSession, branch_id: UUID) -> List[str]:
    """Get all supervisor user IDs in a given branch."""
    stmt = (
        select(Employee)
        .options(joinedload(Employee.user).joinedload(User.role))
        .filter(Employee.branch_id == branch_id)
        .filter(Employee.is_active == True)
    )
    result = await session.execute(stmt)
    employees = result.unique().scalars().all()
    
    # Filter employees with supervisor role
    supervisor_ids = []
    for emp in employees:
        if emp.user and emp.user.role:
            role_name = emp.user.role.name.lower()
            if role_name == "supervisor":
                supervisor_ids.append(str(emp.user_id))
    
    return supervisor_ids


async def get_branch_manager_id(session: AsyncSession, branch_id: UUID) -> str | None:
    """Get the branch manager user ID for a given branch."""
    from models.role import Role
    
    stmt = (
        select(Employee)
        .join(User, Employee.user_id == User.id)
        .join(Role, User.role_id == Role.id)
        .filter(
            Employee.branch_id == branch_id,
            Role.name == "branch manager"
        )
    )
    result = await session.execute(stmt)
    branch_manager = result.scalars().first()
    
    return str(branch_manager.user_id) if branch_manager else None


async def administrative_user_id(session: AsyncSession, role_name: str) -> List[str]:
    """Get the branch manager user ID for a given branch."""
    from models.role import Role
    
    stmt = (
        select(Employee)
        .join(User, Employee.user_id == User.id)
        .join(Role, User.role_id == Role.id)
        .filter(
            Role.name == role_name
        )
    )
    result = await session.execute(stmt)
    users = result.scalars().all()

    user_ids = []
    for user in users:
        user_ids.append(str(user.user_id))
    
    return user_ids