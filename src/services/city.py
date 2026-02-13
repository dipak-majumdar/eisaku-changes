from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from core import messages
from models import City as Model
from schemas import (
    CityList as ListSchema,
    CityRead as ReadSchema,
    CityCreate as CreateSchema,
    CityUpdate as UpdateSchema
)


OBJECT_NOT_FOUND = messages.CITY_NOT_FOUND
OBJECT_EXIST = messages.CITY_EXIST
OBJECT_DELETED = messages.CITY_DELETED


class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_object(self, id: UUID) -> Model:
        statement = select(Model).where(Model.id == id)
        result = await self.session.execute(statement)
        obj = result.unique().scalars().first()
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=OBJECT_NOT_FOUND
            )
        return obj
    
    async def _save(self, obj: Model) -> Model:
        """Utility: add + commit + refresh"""
        try:
            self.session.add(obj)
            await self.session.commit()
            await self.session.refresh(obj)
            return obj
        except IntegrityError as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=OBJECT_EXIST,
            )

    async def _paginate(self, statement, request: Request, page=1, size=10) -> ListSchema:
        # Get total count
        count_stmt = select(func.count()).select_from(statement.subquery())
        total = (await self.session.execute(count_stmt)).scalar()
        
        # Pagination
        offset = (page - 1) * size
        
        # Apply ordering and pagination
        statement = statement.order_by(Model.created_at.desc())
        statement = statement.offset(offset).limit(size)
        
        # Execute and get results
        results = (await self.session.execute(statement)).unique().scalars().all()

        next_url = (
            str(request.url.include_query_params(page=page + 1))
            if offset + size < total else None
        )
        previous_url = (
            str(request.url.include_query_params(page=page - 1))
            if page > 1 else None
        )

        return ListSchema(total=total, next=next_url, previous=previous_url, results=results)

    async def list(self, request: Request, page=1, size=10, search: str | None = None, district_id: UUID | None = None) -> ListSchema:
        statement = select(Model)

        if district_id:
            statement = statement.where(Model.district_id == district_id)

        # ✅ Apply search filter
        if search:
            statement = statement.where(Model.name.ilike(f"%{search}%"))
            
        return await self._paginate(statement, request, page, size)

    async def read(self, request: Request, id: UUID) -> ReadSchema:
        obj = await self.get_object(id)
        return ReadSchema.from_orm(obj)

    async def create(self, request: Request, item: CreateSchema) -> Model:
        user = request.state.user
        obj = Model(**item.dict(), created_by=user.id, updated_by=user.id)
        return await self._save(obj)

    async def update(self, request: Request, id: UUID, item: UpdateSchema) -> Model:
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
