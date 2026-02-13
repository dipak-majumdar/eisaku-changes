from uuid import UUID
from datetime import date, datetime
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from fastapi import HTTPException, Request, status, UploadFile
import os
import aiofiles
from sqlalchemy.exc import IntegrityError

from core import messages
from models import CustomerAgreement as Model
from models.enums import TimePeriodEnum
from schemas import (
    CustomerAgreementList as ListSchema,
    CustomerAgreementRead as ReadSchema,
    CustomerAgreementCreate as CreateSchema,
    CustomerAgreementUpdate as UpdateSchema,
)
from utils.date_helpers import get_date_range

OBJECT_NOT_FOUND = messages.Customer_AGREEMENT_NOT_FOUND
OBJECT_EXIST = messages.Customer_AGREEMENT_EXIST
OBJECT_DELETED = messages.Customer_AGREEMENT_DELETED


async def save_upload_file(upload_file: UploadFile, upload_dir: str) -> str:
    """Save uploaded file and return path"""
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{upload_file.filename}"
    file_path = os.path.join(upload_dir, filename)
    
    # Use aiofiles for async file writing
    async with aiofiles.open(file_path, "wb") as f:
        content = await upload_file.read()
        await f.write(content)
    
    return file_path.replace('\\', '/')


class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_object(self, id: UUID) -> Model:
        """Get object by ID"""
        obj = await self.session.get(Model, id)
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
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=OBJECT_EXIST,
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

        read_results = [ReadSchema.model_validate(obj) for obj in results]
        return ListSchema(total=total, next=next_url, previous=previous_url, results=read_results)

    async def list(
        self, 
        request: Request, 
        page=1, 
        size=10, 
        customer_id: UUID | None = None,
        search: str | None = None,
        time_period: TimePeriodEnum | None = None,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> ListSchema:
        """List customer agreements with filters and pagination"""
        query = select(Model)
        
        # Apply date filters
        date_start, date_end = get_date_range(time_period, start_date, end_date)
        if date_start:
            query = query.filter(Model.created_at >= date_start)
        if date_end:
            query = query.filter(Model.created_at <= date_end)
        
        # Apply search filter
        if search:
            query = query.filter(Model.name.ilike(f"%{search}%"))
        
        # Filter by customer_id
        if customer_id:
            query = query.filter(Model.customer_id == customer_id)
        
        return await self._paginate(query, request, page, size)

    async def read(self, request: Request, id: UUID) -> ReadSchema:
        """Read single customer agreement by ID"""
        obj = await self.get_object(id)
        return ReadSchema.model_validate(obj)

    async def create(
        self, 
        request: Request, 
        item: CreateSchema,
        agreement_document: UploadFile
    ) -> ReadSchema:
        """Create customer agreement with document upload"""
        # Save uploaded document
        upload_dir = "uploads/customer_agreements"
        document_path = await save_upload_file(agreement_document, upload_dir)
        
        # Create agreement with document path
        obj = Model(**item.dict(), agreement_document=document_path)
        return ReadSchema.model_validate(await self._save(obj))

    async def update(
        self, 
        request: Request, 
        id: UUID, 
        item: UpdateSchema,
        agreement_document: UploadFile | None = None
    ) -> ReadSchema:
        """Update customer agreement with optional document upload"""
        obj = await self.get_object(id)
        
        # Update fields from item
        for key, value in item.dict(exclude_unset=True).items():
            setattr(obj, key, value)
        
        # Update document if provided
        if agreement_document:
            upload_dir = "uploads/customer_agreements"
            document_path = await save_upload_file(agreement_document, upload_dir)
            obj.agreement_document = document_path
        
        return ReadSchema.model_validate(await self._save(obj))

    async def delete(self, request: Request, id: UUID):
        """Delete customer agreement"""
        obj = await self.get_object(id)
        await self.session.delete(obj)
        await self.session.commit()
        return {"detail": OBJECT_DELETED}

    async def toggle_active(self, request: Request, id: UUID):
        """Toggle active status of customer agreement"""
        obj = await self.get_object(id)
        obj.is_active = not obj.is_active
        obj.updated_at = datetime.utcnow()
        return await self._save(obj)
