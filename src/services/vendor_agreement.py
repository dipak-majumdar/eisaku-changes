from uuid import UUID
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from fastapi import HTTPException, Request, status, UploadFile
import os
from sqlalchemy.exc import IntegrityError

from core import messages
from models import VendorAgreement as Model
from models.enums import TimePeriodEnum
from schemas.vendor_agreement import (
    VendorAgreementList as ListSchema,
    VendorAgreementRead as ReadSchema,
    VendorAgreementCreate as CreateSchema,
    VendorAgreementUpdate as UpdateSchema,
)
from utils.date_helpers import get_date_range

OBJECT_NOT_FOUND =messages.VENDOR_AGREEMENT_NOT_FOUND
OBJECT_EXIST = messages.VENDOR_AGREEMENT_EXIST
OBJECT_DELETED = messages.VENDOR_AGREEMENT_DELETED



def save_upload_file(upload_file: UploadFile, upload_dir: str) -> str:
    """Save uploaded file and return path"""
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{upload_file.filename}"
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as f:
        f.write(upload_file.file.read())
    return file_path.replace('\\', '/')

class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_object(self, id: UUID) -> Model:
        statement = select(Model).where(Model.id == id)
        result = await self.session.execute(statement)
        obj = result.scalars().first()
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

    async def _paginate(self, statement, request: Request, page=1, size=10) -> ListSchema:
        count_stmt = select(func.count()).select_from(statement.subquery())
        total = (await self.session.execute(count_stmt)).scalar()
        
        offset = (page - 1) * size
        statement = statement.order_by(Model.created_at.desc()).offset(offset).limit(size)
        
        results = (await self.session.execute(statement)).scalars().all()

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

    async def list(self, request: Request, page=1, size=10, vendor_id: UUID | None = None,search: str | None = None,time_period: TimePeriodEnum | None = None,  start_date: date | None = None,  end_date: date | None = None, ) -> ListSchema:
        statement = select(Model)
        date_start, date_end = get_date_range(time_period, start_date, end_date)
        if date_start:
            statement = statement.where(Model.created_at >= date_start)
        if date_end:
            statement = statement.where(Model.created_at <= date_end)
        if search:
            statement = statement.where(Model.name.ilike(f"%{search}%"))
        if vendor_id:
            statement = statement.where(Model.vendor_id == vendor_id)
        return await self._paginate(statement, request, page, size)

    async def read(self, request: Request, id: UUID) -> ReadSchema:
        obj = await self.get_object(id)
        return ReadSchema.model_validate(obj)

  
    async def create(
        self, 
        request: Request, 
        item: CreateSchema,
        agreement_document: UploadFile
    ) -> ReadSchema:
        """Create vendor agreement with document upload"""
        # Save uploaded document
        upload_dir = "uploads/vendor_agreements"
        document_path = save_upload_file(agreement_document, upload_dir)
        
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
        """Update vendor agreement with optional document upload"""
        obj = await self.get_object(id)
        
        # Update fields from item
        for key, value in item.dict(exclude_unset=True).items():
            setattr(obj, key, value)
        
        # Update document if provided
        if agreement_document:
            upload_dir = "uploads/vendor_agreements"
            document_path = save_upload_file(agreement_document, upload_dir)
            obj.agreement_document = document_path
        
        return ReadSchema.model_validate(await self._save(obj))

    async def delete(self, request: Request, id: UUID):
        obj = await self.get_object(id)
        await self.session.delete(obj)
        await self.session.commit()
        return {"detail": OBJECT_DELETED}
