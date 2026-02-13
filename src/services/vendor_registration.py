from uuid import UUID
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from fastapi import HTTPException, Request, status, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from typing import Optional
import os

from core import messages
from models import VendorRegistration as Model, VehicleType
from models.enums import TimePeriodEnum
from models.vendor_registation import VendorRegistrationStatusEnum
from schemas.vendor_resigtration import (
    VendorRegistrationList as ListSchema,
    VendorRegistrationRead as ReadSchema,
    VendorRegistrationCreate as CreateSchema,
    VendorRegistrationUpdate as UpdateSchema,
    VendorRegistrationStatusUpdate,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
)
from schemas.branch import IdName, AddressRead
from utils.date_helpers import get_date_range


OBJECT_NOT_FOUND = messages.VENDOR_REGISTRATION_NOT_FOUND
OBJECT_EXIST = messages.VENDOR_REGISTRATION_EXIST
OBJECT_DELETED = messages.VENDOR_REGISTRATION_DELETED

def save_upload_file(upload_file: UploadFile, upload_dir: str) -> str:
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
        statement = select(Model).where(Model.id == id).options(selectinload(Model.vehicle_types))
        result = await self.session.execute(statement)
        obj = result.scalars().first()
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=OBJECT_NOT_FOUND
            )
        return obj

    async def _paginate(self, statement, request: Request, page=1, size=10) -> ListSchema:
        count_stmt = select(func.count()).select_from(statement.subquery())
        total = (await self.session.execute(count_stmt)).scalar()
        
        offset = (page - 1) * size
        statement = statement.order_by(Model.created_at.desc()).offset(offset).limit(size)
        
        results = (await self.session.execute(statement)).unique().scalars().all()

        next_url = (
            str(request.url.include_query_params(page=page + 1))
            if offset + size < total else None
        )
        previous_url = (
            str(request.url.include_query_params(page=page - 1))
            if page > 1 else None
        )

        results = [self._to_read_schema(obj) for obj in results]
        return ListSchema(total=total, next=next_url, previous=previous_url, results=results)

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
                detail=messages.VENDOR_REGISTRATION_EXIST,
            )

    def _to_read_schema(self, obj: Model) -> ReadSchema:
        from schemas.vendor_resigtration import VehicleTypeLink
        address = AddressRead(
            pin_code=obj.pin_code,
            location=obj.location,
            country=IdName(id=obj.country.id, name=obj.country.name) if obj.country else None,
            state=IdName(id=obj.state.id, name=obj.state.name) if obj.state else None,
            district=IdName(id=obj.district.id, name=obj.district.name) if obj.district else None,
            city=IdName(id=obj.city.id, name=obj.city.name) if obj.city else None,
        )

        vehicle_types = [
            VehicleTypeLink(id=vt.id, name=vt.name) for vt in obj.vehicle_types
        ]

        return ReadSchema(
            id=obj.id,
            transporter_firm_name=obj.transporter_firm_name,
            owner_name=obj.owner_name,
            contact_number=obj.contact_number,
            gst_number=obj.gst_number,
            gst_document=obj.gst_document,
            pan_card_number=obj.pan_card_number,
            pan_card_document=obj.pan_card_document,
            region_id=obj.region_id,
            total_vehicle_owned=obj.total_vehicle_owned,
            route=obj.route,
            visiting_card=obj.visiting_card,
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            created_by=obj.created_by,
            updated_by=obj.updated_by,
            address=address,
            region=IdName(id=obj.region.id, name=obj.region.name) if obj.region else None,
            vehicle_types=vehicle_types,
            status=obj.status,
        )

    async def list(
        self, 
        request: Request, 
        page=1, 
        size=10, 
        search: str | None = None, 
        status: VendorRegistrationStatusEnum | None = None,
        time_period: TimePeriodEnum | None = None, 
        start_date: date | None = None, 
        end_date: date | None = None,
    ) -> ListSchema:
        from models.user import User
        from models.employee import Employee
        from models.role import Role
        
        current_user = request.state.user
        
        # Base statement
        statement = select(Model).options(
            selectinload(Model.vehicle_types),
            selectinload(Model.country),
            selectinload(Model.state),
            selectinload(Model.district),
            selectinload(Model.city),
            selectinload(Model.region)
        )
        
        # ✅ Branch-based filtering (skip for admin/national manager)
        user_role_name = current_user.role.name.lower() if current_user.role else ""
        
        # Skip branch filtering for these roles
        skip_branch_filter_roles = ["admin", "national manager", "corporate admin"]
        
        if user_role_name not in skip_branch_filter_roles:
            # Get current user's branch_id from their employee record
            employee_stmt = select(Employee).where(Employee.user_id == current_user.id)
            employee_result = await self.session.execute(employee_stmt)
            current_employee = employee_result.scalars().first()
            
            if current_employee and current_employee.branch_id:
                current_branch_id = current_employee.branch_id
                
                # Subquery to find all users from the same branch
                same_branch_users_sq = (
                    select(User.id)
                    .join(Employee, User.id == Employee.user_id)
                    .where(Employee.branch_id == current_branch_id)
                )
                
                # Filter vendor registrations created by users from the same branch
                statement = statement.where(Model.created_by.in_(same_branch_users_sq))
        
        # Date filtering
        date_start, date_end = get_date_range(time_period, start_date, end_date)
        if date_start:
            statement = statement.where(Model.created_at >= date_start)
        if date_end:
            statement = statement.where(Model.created_at <= date_end)
        
        # Search filtering
        if search:
            from sqlalchemy import or_
            statement = statement.where(
                or_(
                    Model.transporter_firm_name.ilike(f"%{search}%"),
                    Model.owner_name.ilike(f"%{search}%"),
                    Model.contact_number.ilike(f"%{search}%"),
                    Model.gst_number.ilike(f"%{search}%"),
                    Model.pan_card_number.ilike(f"%{search}%")
                )
            )
        
        # Status filtering
        if status:
            statement = statement.where(Model.status == status)
        
        return await self._paginate(statement, request, page, size)


    async def read(self, request: Request, id: UUID) -> ReadSchema:
        obj = await self.get_object(id)
        return self._to_read_schema(obj)

    async def create(self, request: Request, item: CreateSchema, gst_document: Optional[UploadFile] = None, pan_card_document: Optional[UploadFile] = None, visiting_card: Optional[UploadFile] = None) -> ReadSchema:
        user = request.state.user
        
        address_data = item.address
        vendor_data = item.dict(exclude={'address', 'vehicle_type_ids'})
        
        upload_dir = "uploads/vendor_documents"
        if gst_document:
            vendor_data['gst_document'] = save_upload_file(gst_document, upload_dir)
        if pan_card_document:
            vendor_data['pan_card_document'] = save_upload_file(pan_card_document, upload_dir)
        if visiting_card:
            vendor_data['visiting_card'] = save_upload_file(visiting_card, upload_dir)

        vehicle_types_result = await self.session.execute(
            select(VehicleType).where(VehicleType.id.in_(item.vehicle_type_ids))
        )
        vehicle_types = vehicle_types_result.unique().scalars().all()

        obj = Model(**vendor_data, **address_data.dict(), created_by=user.id, updated_by=user.id)
        obj.vehicle_types = list(vehicle_types)
        
        saved_obj = await self._save(obj)
        created_obj = await self.get_object(saved_obj.id)
        return self._to_read_schema(created_obj)

    async def update(self, request: Request, id: UUID, item: UpdateSchema, gst_document: Optional[UploadFile] = None, pan_card_document: Optional[UploadFile] = None, visiting_card: Optional[UploadFile] = None) -> ReadSchema:
        user = request.state.user
        obj = await self.get_object(id)
        
        update_data = item.dict(exclude_unset=True)
        
        upload_dir = "uploads/vendor_documents"
        if gst_document:
            update_data['gst_document'] = save_upload_file(gst_document, upload_dir)
        if pan_card_document:
            update_data['pan_card_document'] = save_upload_file(pan_card_document, upload_dir)
        if visiting_card:
            update_data['visiting_card'] = save_upload_file(visiting_card, upload_dir)

        if 'address' in update_data:
            address_data = update_data.pop('address')
            for key, value in address_data.items():
                setattr(obj, key, value)
        
        if 'vehicle_type_ids' in update_data:
            vehicle_type_ids = update_data.pop('vehicle_type_ids')
            vehicle_types_result = await self.session.execute(
                select(VehicleType).where(VehicleType.id.in_(vehicle_type_ids))
            )
            vehicle_types = vehicle_types_result.unique().scalars().all()
            obj.vehicle_types = list(vehicle_types)

        for key, value in update_data.items():
            setattr(obj, key, value)

        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()
        saved_obj = await self._save(obj)
        updated_obj = await self.get_object(saved_obj.id)
        return self._to_read_schema(updated_obj)

    async def delete(self, request: Request, id: UUID):
        obj = await self.get_object(id)
        await self.session.delete(obj)
        await self.session.commit()
        return {"detail": messages.VENDOR_REGISTRATION_DELETED}

    async def update_status(self, request: Request, id: UUID, item: VendorRegistrationStatusUpdate) -> ReadSchema:
        user = request.state.user
        obj = await self.get_object(id)
        obj.status = item.status
        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()
        saved_obj = await self._save(obj)
        return self._to_read_schema(saved_obj)

    async def check_duplicate(self, item: DuplicateCheckRequest) -> DuplicateCheckResponse:
        
        statement = select(Model)
        
        if item.type == 'gst':
            statement = statement.where(Model.gst_number == item.number)
            result = await self.session.execute(statement)
            existing_registration = result.scalars().first()
            if existing_registration:
                return DuplicateCheckResponse(
                    is_available=False,
                    message=f"GST number '{item.number}' is already occupied."
                )
            return DuplicateCheckResponse(
                is_available=True,
                message="GST number is available."
            )
        
        elif item.type == 'pan':
            statement = statement.where(Model.pan_card_number == item.number)
            result = await self.session.execute(statement)
            existing_registration = result.scalars().first()
            if existing_registration:
                return DuplicateCheckResponse(
                    is_available=False,
                    message=f"PAN number '{item.number}' is already occupied."
                )
            return DuplicateCheckResponse(
                is_available=True,
                message="PAN number is available."
            )
