from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select
from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from core import messages
from models import Permission as Model
from schemas import PermissionList as ListSchema



OBJECT_NOT_FOUND = messages.PERMISSION_NOT_FOUND
OBJECT_EXIST = messages.PERMISSION_EXIST
OBJECT_DELETED = messages.PERMISSION_DELETED



class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_object(self, id: UUID) -> Model:
        result = await self.session.execute(select(Model).where(Model.id == id))
        obj = result.scalars().first()
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
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=OBJECT_EXIST,
            )

    async def list(self, request: Request, search: str | None = None) -> ListSchema:
        query = select(Model)

        # Apply search filter
        if search:
            query = query.where(Model.model_name.ilike(f"%{search}%"))
        
        # Get all results without pagination
        result = await self.session.execute(query)
        results = result.scalars().all()
        
        return ListSchema(results=results)

    async def read(self, request: Request, id: UUID) -> Model:
        return await self.get_object(id)
    
    async def create(self, request: Request, item: Model):
        user = request.state.user# Convert schema → dict
        obj = Model(**item.dict())  # ✅ Convert to table model
        return await self._save(obj)

    async def update(self, request: Request, id: UUID, item: Model):
        user = request.state.user
        obj = await self.get_object(id)
        
        # ✅ Update only the fields that were set
        for key, value in item.dict(exclude_unset=True).items():
            setattr(obj, key, value)

        return await self._save(obj)

    async def delete(self, request: Request, id: UUID):
        obj = await self.get_object(id)
        await self.session.delete(obj)
        await self.session.commit()
        return {"detail": OBJECT_DELETED}
    
