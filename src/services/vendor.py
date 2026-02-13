from uuid import UUID
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, case, func, select
from fastapi import HTTPException, Request, status, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
import os
from models import Vendor as Model

from passlib.context import CryptContext

from core import messages

from models import (
    Vendor,
    VendorRegistration,
    User,
    Role,
    VehicleType,
    VendorContactPerson,
    VendorAgreement,
    VendorBankDetails,
    Branch,
    Country,
    State,
    District,
    City,
    Region,
)
from models.enums import TimePeriodEnum
from models.vendor import VendorStatusEnum, VendorTypeEnum
from models.vendor_registation import VendorRegistrationStatusEnum
from schemas.contact_person import ContactPersonRead
from schemas.vendor import (
    VendorList as ListSchema,
    VendorRead as ReadSchema,
    AddressRead,
    DocumentDetails,
    VendorUpdate,
)
from schemas.branch import IdName, CountryIdName, StateIdName, DistrictIdName, CityIdName
from services.vendor_registration import save_upload_file
from utils.date_helpers import get_date_range
from utils.get_region import get_states_by_region



OBJECT_NOT_FOUND = messages.VENDOR_NOT_FOUND
OBJECT_EXIST = messages.VENDOR_EXIST
OBJECT_DELETED = messages.VENDOR_DELETED


class VendorService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)
    
    
    def _to_read_schema(self, obj: Vendor) -> ReadSchema:
        from schemas.vendor import VehicleTypeLink, VendorAgreementRead, VendorBankDetailsRead
        
        address = AddressRead(
            pin_code=obj.pin_code,
            location=obj.location,
            country=CountryIdName(id=obj.country.id, name=obj.country.name) if obj.country else None,
            state=StateIdName(id=obj.state.id, name=obj.state.name) if obj.state else None,
            district=DistrictIdName(id=obj.district.id, name=obj.district.name) if obj.district else None,
            city=CityIdName(id=obj.city.id, name=obj.city.name) if obj.city else None,
        )

        documents = DocumentDetails(
            gst_number=obj.gst_number,
            gst_document=obj.gst_document,
            pan_number=obj.pan_number,
            pan_document=obj.pan_document,
            address_document_type=obj.address_document_type,
            address_document=obj.address_document,
            )


        return ReadSchema(
            id=obj.id,
            vendor_code=obj.vendor_code,
            vendor_name=obj.vendor_name,
            branch=IdName(id=obj.branch.id, name=obj.branch.name) if obj.branch else None,
            vendor_type=obj.vendor_type,
            vendor_profile=obj.vendor_profile,
          
            credit_period=obj.credit_period,
            operation_zone=obj.operation_zone,
            route=obj.route,
            status=obj.status,
            reject_reason=obj.reject_reason, 
            address=address,
            documents=documents,
         
            vehicle_types=[VehicleTypeLink(id=vt.id, name=vt.name) for vt in obj.vehicle_types],
            contact_persons=[ContactPersonRead.from_orm(cp) for cp in obj.contact_persons],
            agreements=[VendorAgreementRead.from_orm(ag) for ag in obj.agreements],
            bank_details=[VendorBankDetailsRead.from_orm(bd) for bd in obj.bank_details],
            origin=CityIdName(id=obj.origin.id, name=obj.origin.name) if obj.origin else None,  # ADD THIS
            destination=CityIdName(id=obj.destination.id, name=obj.destination.name) if obj.destination else None,  # ADD THIS
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            created_by=obj.created_by,
            updated_by=obj.updated_by,
        )
    
    async def _calculate_statistics(self, base_stmt) -> dict:
        """
        Calculate vendor statistics - simpler and more reliable approach
        """
        # Count total
        total_stmt = select(func.count()).select_from(
            base_stmt.with_only_columns(Vendor.id).subquery()
        )
        total = (await self.session.execute(total_stmt)).scalar() or 0
        
        # Count approved
        approved_stmt = select(func.count()).select_from(
            base_stmt.where(Vendor.status == VendorStatusEnum.APPROVED)
            .with_only_columns(Vendor.id).subquery()
        )
        approved = (await self.session.execute(approved_stmt)).scalar() or 0
        
        # Count pending
        pending_stmt = select(func.count()).select_from(
            base_stmt.where(Vendor.status == VendorStatusEnum.PENDING)
            .with_only_columns(Vendor.id).subquery()
        )
        pending = (await self.session.execute(pending_stmt)).scalar() or 0
        
        # Count rejected
        rejected_stmt = select(func.count()).select_from(
            base_stmt.where(Vendor.status == VendorStatusEnum.REJECTED)
            .with_only_columns(Vendor.id).subquery()
        )
        rejected = (await self.session.execute(rejected_stmt)).scalar() or 0
        
        return {
            "total": total,
            "approved": approved,
            "pending": pending,
            "rejected": rejected
        }



    
    async def _paginate(self, statement, request: Request, page=1, size=10, base_statement=None) -> ListSchema:
        stmt_for_stats = base_statement if base_statement is not None else statement
        statistics = await self._calculate_statistics(stmt_for_stats)
        total = statistics["total"]

        # Pagination 
        offset = (page - 1) * size
        limit = size
        statement = statement.order_by(Model.created_at.desc())  # ordering
        statement = statement.offset(offset).limit(limit)
        results = (await self.session.execute(statement)).scalars().all()

        next_url = str(request.url.include_query_params(page=page + 1)) if offset + size < total else None
        previous_url = str(request.url.include_query_params(page=page - 1)) if page > 1 else None

        return ListSchema(total=total, next=next_url, previous=previous_url, statistics=statistics, results=results)

    async def get_object(self, id: UUID) -> Vendor:
        query = select(Vendor).options(
            selectinload(Vendor.vehicle_types),
            selectinload(Vendor.contact_persons),
            selectinload(Vendor.agreements),
            selectinload(Vendor.bank_details),
            selectinload(Vendor.origin), 
            selectinload(Vendor.destination),
            selectinload(Vendor.branch),
            selectinload(Vendor.country),
            selectinload(Vendor.state),
            selectinload(Vendor.district),
            selectinload(Vendor.city),
        ).where(Vendor.id == id)
        
        result = await self.session.execute(query)
        obj = result.scalars().first()
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor not found",
            )
        return obj

    async def list(
        self, 
        request: Request, 
        page: int = 1, 
        size: int = 10, 
        search: str | None = None, 
        vendor_type: VendorTypeEnum | None = None, 
        branch_id: UUID | None = None, 
        region_id: UUID | None = None, 
        time_period: TimePeriodEnum | None = None, 
        start_date: date | None = None, 
        end_date: date | None = None,
        status: VendorStatusEnum | None = None
    ) -> ListSchema:
        from models.employee import Employee
        
        current_user = request.state.user
        
        # Optimized query - build base statement first
        base_statement = select(Model)
        
        # ✅ NEW: Branch-based filtering for users with branch assignment
        # Get current user's branch_id from their employee record
        employee_stmt = select(Employee).where(Employee.user_id == current_user.id)
        employee_result = await self.session.execute(employee_stmt)
        current_employee = employee_result.scalars().first()
        
        # ✅ Role-based bypass for admins/national managers
        user_role_name = current_user.role.name.lower() if current_user.role else ""
        skip_branch_filter_roles = ["admin", "national manager", "corporate admin"]
        
        if current_employee and current_employee.branch_id and user_role_name not in skip_branch_filter_roles:
           
            base_statement = base_statement.where(Vendor.branch_id == current_employee.branch_id)
        elif branch_id:
        
            base_statement = base_statement.where(Vendor.branch_id == branch_id)

        # Filter by vendor type
        if vendor_type:
            base_statement = base_statement.where(Vendor.vendor_type == vendor_type)
        if status:
            base_statement = base_statement.where(Vendor.status == status)
        
        # Region filtering
        if region_id:
            region = await self.session.get(Region, region_id)
            if not region:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Region with id {region_id} not found"
                )
            region_name = region.name.lower()

            if region_name:
                states_in_region = get_states_by_region(region_name)
                base_statement = base_statement.where(
                    Vendor.state.has(State.name.in_(states_in_region))
                )
        
        # Search filtering
        if search:
            base_statement = base_statement.where(
                (Vendor.vendor_name.ilike(f"%{search}%"))
                | (Vendor.vendor_code.ilike(f"%{search}%"))
                | (Vendor.gst_number.ilike(f"%{search}%"))
                | (Vendor.pan_number.ilike(f"%{search}%"))
            )

        # Date filtering
        if time_period:
            start_date, end_date = get_date_range(time_period, start_date, end_date)

        if start_date and end_date and not time_period:
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.max.time())

        if start_date and end_date:
            base_statement = base_statement.where(
                Vendor.created_at >= start_date, 
                Vendor.created_at <= end_date
            )
        
        # Add options for result fetching
        statement = base_statement.options(
            selectinload(Vendor.branch).load_only(Branch.id, Branch.name),
            selectinload(Vendor.vehicle_types),
            selectinload(Vendor.contact_persons),
            selectinload(Vendor.agreements),
            selectinload(Vendor.bank_details),
            selectinload(Vendor.origin),
            selectinload(Vendor.destination),
            selectinload(Vendor.country),
            selectinload(Vendor.state),
            selectinload(Vendor.district),
            selectinload(Vendor.city),
        )

        return await self._paginate(statement, request, page, size, base_statement=base_statement)
    
    async def list_all(
        self, 
        request: Request, 
        search: str | None = None, 
        vendor_type: VendorTypeEnum | None = None, 
        branch_id: UUID | None = None, 
        time_period: TimePeriodEnum | None = None, 
        start_date: date | None = None, 
        end_date: date | None = None,
        status: VendorStatusEnum | None = None
    ):
        """List all vendors without pagination"""
        from schemas.vendor import VendoropenList  # Import here if needed
        
        statement = select(Model).options(
            selectinload(Vendor.branch).load_only(Branch.id, Branch.name),
            selectinload(Vendor.vehicle_types),
            selectinload(Vendor.contact_persons),
            selectinload(Vendor.agreements),
            selectinload(Vendor.bank_details),
            selectinload(Vendor.origin),
            selectinload(Vendor.destination),
            selectinload(Vendor.country),
            selectinload(Vendor.state),
            selectinload(Vendor.district),
            selectinload(Vendor.city),
        )

        # Apply all filters (same as regular list)
        if vendor_type:
            statement = statement.where(Vendor.vendor_type == vendor_type)
        if status:
            statement = statement.where(Vendor.status == status)
        if branch_id:
            statement = statement.where(Vendor.branch_id == branch_id)
        
        if search:
            statement = statement.where(
                (Vendor.vendor_name.ilike(f"%{search}%"))
                | (Vendor.vendor_code.ilike(f"%{search}%"))
                | (Vendor.gst_number.ilike(f"%{search}%"))
                | (Vendor.pan_number.ilike(f"%{search}%"))
            )

        if time_period:
            start_date, end_date = get_date_range(time_period, start_date, end_date)

        if start_date and end_date and not time_period:
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.max.time())

        if start_date and end_date:
            statement = statement.where(Vendor.created_at >= start_date, Vendor.created_at <= end_date)

        # ✅ Calculate statistics (same logic as paginated version)
        statistics = await self._calculate_statistics(statement)
        
        # ✅ Execute query and get all results
        statement = statement.order_by(Model.created_at.desc())
        results = (await self.session.execute(statement)).scalars().all()
        
        # ✅ Return with statistics
        return VendoropenList(
            total=len(results),
            statistics=statistics,
            results=results
        )
    async def read(self, request: Request, id: UUID) -> ReadSchema:
        """Get vendor by ID with approval info"""
        obj = await self.get_object(id)
        current_user = request.state.user
        
        # Build response with approval info
        response = self._to_read_schema(obj)
        
        # ✅ Add approved_by field based on vendor type
        if obj.vendor_type == VendorTypeEnum.ADVANCE_VENDOR:
            # Advance: Check if current user created this vendor
            if current_user.id == obj.created_by:
                response_dict = response.dict()
                response_dict["approved_by"] = "me"
                return ReadSchema(**response_dict)
            else:
                response_dict = response.dict()
                response_dict["approved_by"] = "not me"
                return ReadSchema(**response_dict)
        
        elif obj.vendor_type == VendorTypeEnum.CREDIT_VENDOR:
            # Credit: Always accountant approval
            response_dict = response.dict()
            response_dict["approved_by"] = "accountant"
            return ReadSchema(**response_dict)
        
        return response


    async def create(
        self,
        request: Request,
        item_data: Dict[str, Any],
        gst_document: Optional[UploadFile] = None,
        pan_document: Optional[UploadFile] = None,
        address_document: Optional[UploadFile] = None,
        bank_document: Optional[UploadFile] = None,
    ) -> ReadSchema:        
        try:
            # with self.session.begin_nested():
            reg_id = item_data.get("registration_id")
            vendor_reg = await self.session.get(VendorRegistration, reg_id)
            if not vendor_reg:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor registration not found")

            vendor_reg.status = VendorRegistrationStatusEnum.APPROVED

            branch_id = item_data.get("branch_id")
            branch = await self.session.get(Branch, branch_id)
            if not branch:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Branch with id {branch_id} not found")

            last_vendor = (await self.session.execute(select(Vendor).order_by(Vendor.vendor_code.desc()))).scalars().first()
            new_code = f"VEN{int(last_vendor.vendor_code.replace('VEN', '')) + 1:03d}" if last_vendor and last_vendor.vendor_code else "VEN001"

            vendor_data = item_data.copy()

            if not vendor_data.get("country_id"):
                vendor_data["country_id"] = vendor_reg.country_id
            if not vendor_data.get("state_id"):
                vendor_data["state_id"] = vendor_reg.state_id
            if not vendor_data.get("district_id"):
                vendor_data["district_id"] = vendor_reg.district_id
            if not vendor_data.get("city_id"):
                vendor_data["city_id"] = vendor_reg.city_id

            upload_dir = "uploads/vendor_documents"
            if gst_document: vendor_data["gst_document"] = save_upload_file(gst_document, upload_dir)
            if pan_document: vendor_data["pan_document"] = save_upload_file(pan_document, upload_dir)
            if address_document: vendor_data["address_document"] = save_upload_file(address_document, upload_dir)

            bank_details_data = vendor_data.pop("bank_details")
            contact_persons_data = vendor_data.pop("contact_persons", [])
            agreements_data = vendor_data.pop("agreements", [])
            vehicle_type_ids = vendor_data.pop("vehicle_type_ids", [])
            vendor = Vendor(**vendor_data, vendor_code=new_code, created_by=request.state.user.id, updated_by=request.state.user.id)
              # ✅ AUTO-APPROVE ADVANCE VENDORS
            if vendor.vendor_type == VendorTypeEnum.ADVANCE_VENDOR:
                vendor.status = VendorStatusEnum.APPROVED
            if item_data.get('vendor_type') == VendorTypeEnum.CREDIT_VENDOR:
                # CHANGED: Use vehicle_type_ids from form data instead of vendor_reg
                if vehicle_type_ids:
                    vehicle_types = (await self.session.execute(select(VehicleType).where(VehicleType.id.in_(vehicle_type_ids)))).scalars().unique().all()
                    vendor.vehicle_types = list(vehicle_types)

            bank_details = VendorBankDetails(**bank_details_data)
            if bank_document: bank_details.document = save_upload_file(bank_document, "uploads/bank_documents")
            vendor.bank_details.append(bank_details)

            if contact_persons_data:
                for cp_data in contact_persons_data:
                    contact_person = VendorContactPerson(**cp_data)
                    vendor.contact_persons.append(contact_person)
            
            if agreements_data:
                for ag_data in agreements_data:
                    agreement = VendorAgreement(**ag_data)
                    vendor.agreements.append(agreement)

            self.session.add(vendor)
            self.session.add(vendor_reg)
            await self.session.flush()
            # ✅ AUTO-CREATE USER FOR APPROVED ADVANCE VENDORS
            if vendor.status == VendorStatusEnum.APPROVED:
                vendor_role = (await self.session.execute(select(Role).where(Role.name == "Vendor"))).scalars().first()
                if not vendor_role:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vendor role not found")

                user_mobile = vendor_reg.contact_number if vendor_reg else (vendor.contact_persons[0].mobile if vendor.contact_persons else vendor.vendor_code)

                user = User(
                    username=vendor.vendor_name,
                    email=f"{vendor.vendor_code}@example.com",
                    mobile=user_mobile,
                    hashed_password=self.hash_password("password"),
                    role_id=vendor_role.id,
                    first_name=vendor.vendor_name,
                )
                self.session.add(user)
                await self.session.flush()
                vendor.user_id = user.id
            await self.session.commit()
            await self.session.refresh(vendor)
            return await self.read(request,vendor.id)

        except IntegrityError as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Data integrity error: {e.orig}")
        except Exception as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {e}")

    async def delete(self, request: Request, id: UUID):
        try:
            # with self.session.begin_nested():
            vendor = await self.get_object(id)
            
            # Find and delete the associated user if they exist
            if vendor.contact_persons:
                user = (await self.session.execute(select(User).where(User.mobile == vendor.contact_persons[0].mobile))).scalars().first()
                if user:
                    self.session.delete(user)

            self.session.delete(vendor)
            await self.session.commit()
            return {"detail": OBJECT_DELETED}
        except Exception as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {e}")

    async def update_status(self, request: Request, id: UUID, new_status: VendorStatusEnum, reject_reason: Optional[str] = None) -> ReadSchema:
        try:
            # with self.session.begin_nested():
            vendor = await self.get_object(id)
            current_user = request.state.user
            
            if new_status == VendorStatusEnum.APPROVED:
                if vendor.vendor_type == VendorTypeEnum.ADVANCE_VENDOR:
                    # Advance: Only creator can approve
                    if current_user.id != vendor.created_by:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only the creator can approve Advance vendors"
                        )
                
                elif vendor.vendor_type == VendorTypeEnum.CREDIT_VENDOR:
                    
                    if not current_user.role or current_user.role.name.lower() not in ["accountant", "accounts", "admin"]:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only Accountant can approve Credit vendors"
                        )
            # Validate reject_reason if status is REJECTED
            if new_status == VendorStatusEnum.REJECTED:
                if not reject_reason or reject_reason.strip() == "":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Reject reason is required when status is REJECTED"
                    )
                vendor.reject_reason = reject_reason
            else:
                vendor.reject_reason = None
            
            vendor.status = new_status
            vendor.updated_by = request.state.user.id
            vendor.updated_at = datetime.utcnow()

            if new_status == VendorStatusEnum.APPROVED:
                vendor_role = (await self.session.execute(select(Role).where(Role.name == "Vendor"))).scalars().first()
                if not vendor_role:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vendor role not found")

                vendor_reg = await self.session.get(VendorRegistration, vendor.registration_id)
                user_mobile = vendor_reg.contact_number if vendor_reg else (vendor.contact_persons[0].mobile if vendor.contact_persons else vendor.vendor_code)

                user = User(
                    username=vendor.vendor_name,
                    email=f"{vendor.vendor_code}@example.com",
                    mobile=user_mobile,
                    hashed_password=self.hash_password("password"),
                    role_id=vendor_role.id,
                    first_name=vendor.vendor_name,
                )
                self.session.add(user)
                await self.session.flush()
                vendor.user_id = user.id

            self.session.add(vendor)

            await self.session.commit()
            await self.session.refresh(vendor)
            return await self.read(request,vendor.id)
        except HTTPException:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {e}")

    async def update(
        self, 
        request: Request, 
        id: UUID, 
        item_data: VendorUpdate,
        gst_document: Optional[UploadFile] = None,
        pan_document: Optional[UploadFile] = None,
        address_document: Optional[UploadFile] = None,
        bank_document: Optional[UploadFile] = None,
        agreement_documents: Optional[List[UploadFile]] = None,  # ✅ Changed to List
    ) -> ReadSchema:
        try:
            vendor = await self.get_object(id)
            update_data = item_data.dict(exclude_unset=True)
            
            upload_dir = "uploads/vendor_documents"
            
            if gst_document:
                update_data['gst_document'] = save_upload_file(gst_document, upload_dir)
            if pan_document:
                update_data['pan_document'] = save_upload_file(pan_document, upload_dir)
            if address_document:
                update_data['address_document'] = save_upload_file(address_document, upload_dir)
            
            bank_details_data = update_data.pop('bank_details', None)
            contact_persons_data = update_data.pop('contact_persons', None)
            agreements_data = update_data.pop('agreements', None)
            vehicle_type_ids = update_data.pop('vehicle_type_ids', None)
            
            # Update basic vendor fields
            for key, value in update_data.items():
                setattr(vendor, key, value)
            
            vendor.updated_by = request.state.user.id
            vendor.updated_at = datetime.utcnow()
            
            # Update bank details
            if bank_details_data:
                bank_details = vendor.bank_details[0] if vendor.bank_details else VendorBankDetails(vendor_id=vendor.id)
                for key, value in bank_details_data.items():
                    setattr(bank_details, key, value)
                if bank_document:
                    bank_details.document = save_upload_file(bank_document, "uploads/bank_documents")
                if not vendor.bank_details:
                    vendor.bank_details.append(bank_details)
            
            # Smart Contact Persons Update
            if contact_persons_data is not None:
                provided_emails = [cp['email'] for cp in contact_persons_data]
                if len(provided_emails) != len(set(provided_emails)):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Duplicate emails found in contact persons data"
                    )
                
                existing_contacts = {cp.email: cp for cp in vendor.contact_persons}
                updated_emails = set()
                contacts_to_delete = []
                
                for cp_data in contact_persons_data:
                    email = cp_data['email']
                    updated_emails.add(email)
                    
                    if email in existing_contacts:
                        existing_contact = existing_contacts[email]
                        existing_contact.name = cp_data.get('name', existing_contact.name)
                        existing_contact.mobile = cp_data.get('mobile', existing_contact.mobile)
                        self.session.add(existing_contact)
                    else:
                        new_contact = VendorContactPerson(**cp_data, vendor_id=vendor.id)
                        self.session.add(new_contact)
                
                for email, contact in existing_contacts.items():
                    if email not in updated_emails:
                        contacts_to_delete.append(contact)
                
                for contact in contacts_to_delete:
                    self.session.delete(contact)
                    self.session.expunge(contact)
            
            
            # ✅ Agreements Update - Delete All and Recreate
            if agreements_data is not None:
                agreement_docs = agreement_documents if agreement_documents else []
                
                # STEP 1: Delete ALL existing agreements
                for existing_agreement in list(vendor.agreements):
                    await self.session.delete(existing_agreement)
                    self.session.expunge(existing_agreement)  # Remove from session tracking
                
                # Flush to ensure deletions are committed
                await self.session.flush()
                
                # STEP 2: Create new agreements from incoming data
                for idx, ag_data in enumerate(agreements_data):
                    # Each agreement must have a document
                    if idx >= len(agreement_docs) or not agreement_docs[idx]:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Agreement at index {idx} requires a document"
                        )
                    
                    # Save the document
                    doc_path = save_upload_file(
                        agreement_docs[idx],
                        "uploads/agreement_documents"
                    )
                    
                    # Create new agreement
                    new_agreement = VendorAgreement(
                        vendor_id=vendor.id,
                        start_date=ag_data.get('start_date'),
                        end_date=ag_data.get('end_date'),
                        agreement_document=doc_path
                    )
                    self.session.add(new_agreement)
            
            
            # Update vehicle types
            if vehicle_type_ids is not None:
                vendor.vehicle_types.clear()
                vehicle_types = (await self.session.execute(
                    select(VehicleType).where(VehicleType.id.in_(vehicle_type_ids))
                )).scalars().unique().all()
                for vt in vehicle_types:
                    vendor.vehicle_types.append(vt)
            
            self.session.add(vendor)
            await self.session.flush()
        
            await self.session.commit()
            
            self.session.expire_all()
            vendor = await self.get_object(id)
            
            return await self.read(request, vendor.id)
        
        except HTTPException:
            await self.session.rollback()
            raise
        except IntegrityError as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Data integrity error: {str(e.orig)}"
            )
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}"
            )



    
    async def check_duplicate(self, gst_number: Optional[str] = None, pan_number: Optional[str] = None, vendor_id: Optional[UUID] = None) -> dict:
        """
        Check if GST number or PAN number already exists for another vendor.
        
        Args:
            gst_number: GST number to check
            pan_number: PAN number to check
            vendor_id: Optional vendor ID to exclude from check (for updates)
        
        Returns:
            Dict with duplicate status and existing vendor details if found
        """
        result = {
            "gst_duplicate": False,
            "pan_duplicate": False,
            "gst_vendor": None,
            "pan_vendor": None,
        }
        
        # Check GST number
        if gst_number:
            query = select(Vendor).where(Vendor.gst_number == gst_number)
            if vendor_id:
                query = query.where(Vendor.id != vendor_id)
            
            existing_vendor = (await self.session.execute(query)).scalars().first()
            if existing_vendor:
                result["gst_duplicate"] = True
                result["gst_vendor"] = {
                    "id": str(existing_vendor.id),
                    "vendor_code": existing_vendor.vendor_code,
                    "vendor_name": existing_vendor.vendor_name,
                    "gst_number": existing_vendor.gst_number,
                }
        
        # Check PAN number
        if pan_number:
            query = select(Vendor).where(Vendor.pan_number == pan_number)
            if vendor_id:
                query = query.where(Vendor.id != vendor_id)
            
            existing_vendor = (await self.session.execute(query)).scalars().first()
            if existing_vendor:
                result["pan_duplicate"] = True
                result["pan_vendor"] = {
                    "id": str(existing_vendor.id),
                    "vendor_code": existing_vendor.vendor_code,
                    "vendor_name": existing_vendor.vendor_name,
                    "pan_number": existing_vendor.pan_number,
                }
        
        return result
    async def update_credit_period(
        self,
        request: Request,
        id: UUID,
        credit_period: int
    ) -> ReadSchema:
        """Update vendor credit period only"""
        try:
            user = request.state.user
            vendor = await self.get_object(id)
            
            vendor.credit_period = credit_period
            vendor.updated_by = user.id
            vendor.updated_at = datetime.utcnow()
            
            self.session.add(vendor)
            await self.session.commit()
            await self.session.refresh(vendor)
            
            return await self.read(request, vendor.id)
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {e}"
            )


    async def update_bank_details(
        self,
        request: Request,
        id: UUID,
        bank_data: dict,
        bank_document: Optional[UploadFile] = None
    ) -> ReadSchema:
        """Update vendor bank details only"""
        try:
            user = request.state.user
            vendor = await self.get_object(id)
            
            # Get or create bank details
            if vendor.bank_details:
                bank_details = vendor.bank_details[0]
            else:
                bank_details = VendorBankDetails(vendor_id=vendor.id)
            
            # Update bank fields
            for key, value in bank_data.items():
                setattr(bank_details, key, value)
            
            # Update document if provided
            if bank_document:
                upload_dir = "uploads/bank_documents"
                doc_path = save_upload_file(bank_document, upload_dir)
                bank_details.document = doc_path
            
            if not vendor.bank_details:
                vendor.bank_details.append(bank_details)
            else:
                self.session.add(bank_details)
            
            vendor.updated_by = user.id
            vendor.updated_at = datetime.utcnow()
            
            self.session.add(vendor)
            await self.session.commit()
            await self.session.refresh(vendor)
            
            return await self.read(request, vendor.id)
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {e}"
            )
