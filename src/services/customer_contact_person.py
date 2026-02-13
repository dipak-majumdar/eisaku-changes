from uuid import UUID
from datetime import date, datetime
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func

from core import messages
from models import CustomerContactPerson as Model
from models.enums import TimePeriodEnum
from schemas import (
    CustomerContactPersonList as ListSchema, 
    CustomerContactPersonRead as ReadSchema, 
    CustomerContactPersonCreate as CreateSchema,
    PermissionReadWithRequired
)
from utils.date_helpers import get_date_range

OBJECT_NOT_FOUND = messages.CONTACT_PERSON_NOT_FOUND
OBJECT_EXIST = messages.CONTACT_PERSON_EXIST
OBJECT_DELETED = messages.CONTACT_PERSON_DELETED


class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_object(self, id: UUID) -> Model:
        """Get object by ID"""
        result = await self.session.execute(
            select(Model).filter(Model.id == id)
        )
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
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=OBJECT_EXIST,
            )
    
    def _validate_contact_person(self, item: CreateSchema | dict) -> None:
        """Validate contact person data"""
        data = item.dict() if hasattr(item, 'dict') else item
        
        # ✅ Validate name
        name = data.get('name')
        if not name or not str(name).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name cannot be empty or whitespace"
            )
        
        # ✅ Validate mobile
        mobile = data.get('mobile')
        if not mobile or not str(mobile).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mobile cannot be empty or whitespace"
            )
        
        # ✅ Validate email
        email = data.get('email')
        if not email or not str(email).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email cannot be empty or whitespace"
            )
        
        # ✅ Validate email format
        email_str = str(email).strip()
        if '@' not in email_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email must contain @ symbol"
            )
        
        domain = email_str.split('@')[-1]
        if '.' not in domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email must have a valid domain (e.g., gmail.com)"
            )
    
    async def _paginate(self, query, request: Request, page=1, size=10) -> ListSchema:
        """Paginate query results"""
        # Count total items
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.scalar(count_query)
        
        # Apply pagination
        offset = (page - 1) * size
        paginated_query = query.order_by(Model.created_at.desc()).offset(offset).limit(size)
        result = await self.session.execute(paginated_query)
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
        end_date: date | None = None
    ) -> ListSchema:
        """List contact persons with filters and pagination"""
        query = select(Model)
        
        # Apply date filters
        date_start, date_end = get_date_range(time_period, start_date, end_date)
        if date_start:
            query = query.filter(Model.created_at >= date_start)
        if date_end:
            query = query.filter(Model.created_at <= date_end)
        
        # ✅ Apply search filter
        if search:
            query = query.filter(Model.name.ilike(f"%{search}%"))
            
        return await self._paginate(query, request, page, size)

    async def read(self, request: Request, id: UUID) -> ReadSchema:
        """Read single contact person by ID"""
        obj = await self.get_object(id)
        return ReadSchema.from_orm(obj)

    async def create(self, request: Request, item: CreateSchema):
        """Create customer contact person with validation"""
        # ✅ Validate input data
        self._validate_contact_person(item)
        
        user = request.state.user
        
        # ✅ Clean and normalize data
        data = item.dict()
        data['name'] = data['name'].strip()
        data['mobile'] = data['mobile'].strip()
        data['email'] = data['email'].strip().lower()
        
        obj = Model(
            **data, 
            created_by=user.id, 
            updated_by=user.id
        )
        return ReadSchema.from_orm(await self._save(obj))

    async def update(self, request: Request, id: UUID, item: CreateSchema):
        """Update customer contact person with validation"""
        user = request.state.user
        obj = await self.get_object(id)
        
        update_data = item.dict(exclude_unset=True)
        
        if update_data:
            # ✅ Validate non-empty values
            for field in ['name', 'mobile', 'email']:
                if field in update_data:
                    value = update_data[field]
                    if not value or not str(value).strip():
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"{field.capitalize()} cannot be empty or whitespace"
                        )
            
            # ✅ Validate email format
            if 'email' in update_data:
                email = str(update_data['email']).strip()
                if '@' not in email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email must contain @ symbol"
                    )
                domain = email.split('@')[-1]
                if '.' not in domain:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email must have a valid domain (e.g., gmail.com)"
                    )
                update_data['email'] = email.lower()
            
            # ✅ Clean data
            if 'name' in update_data:
                update_data['name'] = update_data['name'].strip()
            if 'mobile' in update_data:
                update_data['mobile'] = update_data['mobile'].strip()
            
            for key, value in update_data.items():
                setattr(obj, key, value)
        
        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()

        return ReadSchema.from_orm(await self._save(obj))

    async def delete(self, request: Request, id: UUID):
        """Delete contact person"""
        obj = await self.get_object(id)
        await self.session.delete(obj)
        await self.session.commit()
        return {"detail": OBJECT_DELETED}
    
    async def toggle_active(self, request: Request, id: UUID):
        """Toggle active status of contact person"""
        user = request.state.user
        obj = await self.get_object(id)
        
        # ✅ Update only the is_active, updated_by, updated_at field
        obj.is_active = not obj.is_active
        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()

        return await self._save(obj)
