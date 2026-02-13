from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import json
from fastapi import HTTPException, status, Request
from typing import Optional, List
from datetime import date, datetime
from sqlalchemy import select, or_, func, delete

from models.enums import TimePeriodEnum
from schemas.email import EmailList as ListSchema, EmailRead
from models.email import Email as Model
from utils.date_helpers import get_date_range

OBJECT_NOT_FOUND = "Email details not found"


class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_object(self, id: UUID) -> Model:
        stmt = select(Model).filter(Model.id == id)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=OBJECT_NOT_FOUND
            )
        return obj
    
    def _to_read_schema(self, obj: Model, request: Request) -> EmailRead:
        return EmailRead.model_validate(obj)

    async def _paginate(self, query, request: Request, page: int, size: int):
        # Count total
        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_stmt)).scalar()
        
        offset = (page - 1) * size

        # Get paginated results
        stmt = query.order_by(Model.created_at.desc()).offset(offset).limit(size)
        result = await self.session.execute(stmt)
        results = result.scalars().all()

        next_url = (
            str(request.url.include_query_params(page=page + 1))
            if offset + size < total else None
        )

        previous_url = (
            str(request.url.include_query_params(page=page - 1))
            if page > 1 else None
        )

        converted_results = [self._to_read_schema(obj, request) for obj in results]
        return ListSchema(
            total=total,
            next=next_url,
            previous=previous_url,
            results=converted_results,
        )

    async def list(
        self,
        request: Request,
        page: int = 1,
        size: int = 10,
        search: Optional[str] = None,
        time_period: TimePeriodEnum | None = None, 
        start_date: date | None = None, 
        end_date: date | None = None,
    ) -> ListSchema:
        """List all emails with filters - fetches all emails from database"""
        query = select(Model)

        if search:
            query = query.filter(
                (Model.subject.ilike(f"%{search}%"))
            )

        if time_period:
            start_date, end_date = get_date_range(time_period, start_date, end_date)
        
        if start_date and end_date and not time_period:
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.max.time())
        
        if start_date and end_date:
            query = query.where(Model.created_at >= start_date, Model.created_at <= end_date)
        
        return await self._paginate(query, request, page, size)

    async def read(self, id: UUID, request: Request) -> EmailRead:
        """Read an email"""        
        db_obj = await self.get_object(id)
        return self._to_read_schema(db_obj, request)

    async def bulk_delete(self, email_ids: List[UUID]) -> dict:
        """Delete multiple emails at once"""
        if not email_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email IDs list cannot be empty"
            )
        
        # Check which emails exist
        stmt = select(Model).filter(Model.id.in_(email_ids))
        result = await self.session.execute(stmt)
        existing_emails = result.scalars().all()
        existing_ids = {email.id for email in existing_emails}
        
        # Find missing IDs
        missing_ids = set(email_ids) - existing_ids
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emails not found: {list(missing_ids)}"
            )
        
        # Delete the emails
        delete_stmt = delete(Model).filter(Model.id.in_(email_ids))
        await self.session.execute(delete_stmt)
        await self.session.commit()
        
        return {
            "message": f"Successfully deleted {len(email_ids)} emails",
            "deleted_count": len(email_ids),
            "deleted_ids": email_ids
        }
