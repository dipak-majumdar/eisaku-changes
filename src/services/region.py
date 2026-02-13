from uuid import UUID
from datetime import date, datetime
from sqlalchemy import select, func
from sqlmodel import Session, select as sql_select
from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from core import messages
from models import Region as Model
from models.enums import TimePeriodEnum
from schemas import (
    RegionList as ListSchema,
    RegionRead as ReadSchema,
)
from utils.date_helpers import get_date_range


OBJECT_NOT_FOUND = messages.REGION_NOT_FOUND
OBJECT_EXIST = messages.REGION_EXIST
OBJECT_DELETED = messages.REGION_DELETED


class Service:
    def __init__(self, session: Session):
        self.session = session

    async def get_object(self, id: UUID) -> Model:
        stmt = select(Model).where(Model.id == id)
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=OBJECT_NOT_FOUND
            )
        return obj

    async def _save(self, obj: Model) -> Model:
        try:
            self.session.add(obj)
            await self.session.commit()
            await self.session.refresh(obj)
            return obj
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=OBJECT_EXIST,
            )

    async def _paginate(self, stmt, request: Request, page=1, size=10) -> ListSchema:
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar()
        offset = (page - 1) * size

        paginated_stmt = stmt.order_by(Model.created_at.desc()).offset(offset).limit(size)
        result = await self.session.execute(paginated_stmt)
        results = result.scalars().all()

        next_url = (
            str(request.url.include_query_params(page=page + 1))
            if offset + size < total else None
        )
        previous_url = (
            str(request.url.include_query_params(page=page - 1))
            if page > 1 else None
        )

        return ListSchema(total=total, next=next_url, previous=previous_url, results=results)

    async def list(
        self,
        request: Request,
        page=1,
        size=10,
        search: str | None = None,
        time_period: TimePeriodEnum | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        has_manager: bool | None = None,  # ✅ NEW: Filter by manager presence
    ) -> ListSchema:
        from models.employee import Employee
        from models.user import User
        from models.role import Role
        
        stmt = select(Model)
        
        # Date filtering
        date_start, date_end = get_date_range(time_period, start_date, end_date)
        if date_start:
            stmt = stmt.where(Model.created_at >= date_start)
        if date_end:
            stmt = stmt.where(Model.created_at <= date_end)

        # Search filtering
        if search:
            stmt = stmt.where(Model.name.ilike(f"%{search}%"))
        
        # ✅ NEW: Filter by regional manager presence
        if has_manager is not None:
            # Subquery to find regions that have a regional manager
            regions_with_manager_sq = (
                select(Model.id)
                .join(Employee, Model.id == Employee.region_id)
                .join(User, Employee.user_id == User.id)
                .join(Role, User.role_id == Role.id)
                .where(
                    func.lower(Role.name) == "regional manager",
                    Employee.is_active == True,
                    User.is_active == True
                )
            ).distinct()
            
            if has_manager:
                # Return regions WITH a regional manager
                stmt = stmt.where(Model.id.in_(regions_with_manager_sq))
            else:
                # Return regions WITHOUT a regional manager
                stmt = stmt.where(Model.id.not_in(regions_with_manager_sq))

        return await self._paginate(stmt, request, page, size)

    async def read(self, request: Request, id: UUID) -> ReadSchema:
        obj = await self.get_object(id)
        return ReadSchema.from_orm(obj)

    async def create(self, request: Request, item: Model):
        user = request.state.user
        obj = Model(**item.dict(), created_by=user.id, updated_by=user.id)
        return await self._save(obj)

    async def update(self, request: Request, id: UUID, item: Model):
        user = request.state.user
        obj = await self.get_object(id)

        for key, value in item.dict(exclude_unset=True).items():
            setattr(obj, key, value)

        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()

        return await self._save(obj)

    async def delete(self, request: Request, id: UUID):
        obj = await self.get_object(id)
        await self.session.delete(obj)
        await self.session.commit()
        return {"detail": OBJECT_DELETED}

    async def toggle_active(self, request: Request, id: UUID):
        user = request.state.user
        obj = await self.get_object(id)

        obj.is_active = not obj.is_active
        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()

        return await self._save(obj)
