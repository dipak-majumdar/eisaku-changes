from uuid import UUID
from datetime import date, datetime
from sqlalchemy import case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, func, select
from fastapi import HTTPException, Request, status, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from models import Customer as Model

from typing import Optional, Dict, Any, List
import os
from passlib.context import CryptContext

from core import messages

from models import (
    Customer,
    User,
    Role,
    VehicleType,
    CustomerContactPerson,
    CustomerAgreement,
    Country,
    State,
    District,
    City,
)
from models.customer import CustomerStatusEnum, CustomerTypeEnum, PaymentTerm
from models.enums import TimePeriodEnum
from models.region import Region
from schemas.customer import (
    CustomerList as ListSchema,
    CustomerRead as ReadSchema,
    AddressRead,
    DocumentDetails,
    CustomerUpdate,
    ApprovedCustomerList,
    ApprovedCustomerRead,
)
from schemas.branch import CountryIdName, StateIdName, DistrictIdName, CityIdName
from services.vendor_registration import save_upload_file
from utils.date_helpers import get_date_range
from utils.get_region import get_states_by_region



OBJECT_NOT_FOUND = messages.CUSTOMER_NOT_FOUND
OBJECT_EXIST = messages.CUSTOMER_EXIST
OBJECT_DELETED = messages.CUSTOMER_DELETED



class Service:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)
    
    def _to_read_schema(self, obj: Customer) -> ReadSchema:
        from schemas.customer import VehicleTypeLink, CustomerContactPersonRead, CustomerAgreementRead
        
        # Remove explicit refreshes to avoid N+1 queries
        # if not hasattr(obj, 'country'): self.session.refresh(obj, attribute_names=['country'])
        # ...

        address = AddressRead(
            pin_code=obj.pin_code,
            location=obj.location,
            country=CountryIdName(id=obj.country.id, name=obj.country.name) if obj.country else None,
            state=StateIdName(id=obj.state.id, name=obj.state.name) if obj.state else None,
            district=DistrictIdName(id=obj.district.id, name=obj.district.name) if obj.district else None,
            city=CityIdName(id=obj.city.id, name=obj.city.name) if obj.city else None,
        )

        documents = DocumentDetails(
            gst_number=obj.gst_number or "",
            gst_document=obj.gst_document or "",
            pan_number=obj.pan_number or "",
            pan_document=obj.pan_document or "",
            address_document_type=obj.address_document_type,
            address_document=obj.address_document or "",
        )

        return ReadSchema(
            id=obj.id,
            customer_code=obj.customer_code,
            customer_name=obj.customer_name,
            customer_type=obj.customer_type,
           
            tonnage=obj.tonnage,
            trip_rate=obj.trip_rate,
            credit_period=obj.credit_period,
            status=obj.status,
            address=address,
            documents=documents,
            mobile=obj.mobile,
            email=obj.email,
            payment_term=obj.payment_term,
            vehicle_type=VehicleTypeLink(id=obj.vehicle_type.id, name=obj.vehicle_type.name) if obj.vehicle_type else None,
            contact_persons=[CustomerContactPersonRead.from_orm(cp) for cp in obj.contact_persons],
            agreements=[CustomerAgreementRead.from_orm(ag) for ag in obj.agreements],
            origin=CityIdName(id=obj.origin.id, name=obj.origin.name) if obj.origin else None,
            destination=CityIdName(id=obj.destination.id, name=obj.destination.name) if obj.destination else None,
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            created_by=obj.created_by,
            updated_by=obj.updated_by,
            reject_reason=obj.reject_reason,
        )
    
    async def _calculate_statistics(self, statement) -> dict:
        """Calculate customer statistics based on the current filtered query."""
        # Use func.count() with the session.exec() pattern
        stats_statement = (
            select(
                func.count().label("total"),
                func.count(case((Customer.status == CustomerStatusEnum.APPROVED, 1))).label("approved"),
                func.count(case((Customer.status == CustomerStatusEnum.PENDING, 1))).label("pending"),
                func.count(case((Customer.status == CustomerStatusEnum.REJECTED, 1))).label("rejected"),
            )
            .select_from(statement.subquery())
        )
        
        result = (await self.session.execute(stats_statement)).one()
        return dict(result._mapping)

    async def _paginate(self, statement, request: Request, page=1, size=10, base_statement=None) -> ListSchema:
        # Use base_statement for stats and count if provided
        stmt_for_stats = base_statement if base_statement is not None else statement

        # Calculate statistics first
        statistics = await self._calculate_statistics(stmt_for_stats)
        
        # Get total count using proper SQLAlchemy 2.0 syntax
        if base_statement is not None:
             count_stmt = select(func.count()).select_from(base_statement.with_only_columns(Model.id).subquery())
        else:
             count_stmt = select(func.count()).select_from(statement.subquery())

        total = (await self.session.execute(count_stmt)).scalar()
        
        # Pagination
        offset = (page - 1) * size
        limit = size
        
        # Apply ordering and pagination
        statement = statement.order_by(Model.created_at.desc())
        statement = statement.offset(offset).limit(limit)
        
        # Execute and get results
        results = (await self.session.execute(statement)).scalars().all()
        
        # Generate pagination URLs
        next_url = str(request.url.include_query_params(page=page + 1)) if offset + size < total else None
        previous_url = str(request.url.include_query_params(page=page - 1)) if page > 1 else None
    
        return ListSchema(
            total=total,
            next=next_url,
            previous=previous_url,
            statistics=statistics,
            results=results
        )


    async def get_object(self, id: UUID) -> Customer:
        query = (
            select(Customer)
            .options(
                selectinload(Customer.vehicle_type),
                selectinload(Customer.contact_persons),
                selectinload(Customer.agreements),
                selectinload(Customer.origin),
                selectinload(Customer.destination),
                selectinload(Customer.country),
                selectinload(Customer.state),
                selectinload(Customer.district),
                selectinload(Customer.city),
            )
            .where(Customer.id == id)
        )

        result = await self.session.execute(query)
        obj = result.scalars().first()
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=OBJECT_NOT_FOUND,
            )
        return obj

    async def list(
        self,
        request: Request,
        page: int = 1,
        size: int = 10,
        search: str | None = None,
        region_id: UUID | None = None, 
        customer_type: CustomerTypeEnum | None = None,
        time_period: TimePeriodEnum | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        status: CustomerStatusEnum | None = None
    ) -> ListSchema:
        # Optimized query - build base statement first
        base_statement = select(Customer)

        if region_id:
            region = await self.session.get(Region, region_id)
            if not region:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Region with id {region_id} not found"
                )
            region_name = region.name.lower()

            if region_name:
                states_in_region  = get_states_by_region(region_name)
                base_statement = base_statement.where(
                    Customer.state.has(State.name.in_(states_in_region))
                )
        
        # Apply filters
        if customer_type:
            base_statement = base_statement.where(Customer.customer_type == customer_type)
        if status:
            base_statement = base_statement.where(Customer.status == status)
        if search:
            base_statement = base_statement.where(
                (Customer.customer_name.ilike(f"%{search}%")) |
                (Customer.customer_code.ilike(f"%{search}%")) |
                (Customer.gst_number.ilike(f"%{search}%")) |
                (Customer.pan_number.ilike(f"%{search}%"))
            )
        
        # Date filtering
        if time_period:
            start_date, end_date = get_date_range(time_period, start_date, end_date)
        if start_date and end_date and not time_period:
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.max.time())
        if start_date and end_date:
            base_statement = base_statement.where(
                (Customer.created_at >= start_date) & (Customer.created_at <= end_date)
            )
        
        # Add options for result fetching
        statement = base_statement.options(
            selectinload(Customer.vehicle_type).load_only(VehicleType.id, VehicleType.name),
            selectinload(Customer.country).load_only(Country.id, Country.name),
            selectinload(Customer.state).load_only(State.id, State.name),
            selectinload(Customer.district).load_only(District.id, District.name),
            selectinload(Customer.city).load_only(City.id, City.name),
            selectinload(Customer.origin).load_only(City.id, City.name),
            selectinload(Customer.destination).load_only(City.id, City.name),
            selectinload(Customer.contact_persons),
            selectinload(Customer.agreements),
        )

        return await self._paginate(statement, request, page, size, base_statement=base_statement)


    async def read(self, request: Request, id: UUID) -> ReadSchema:
        """Get customer by ID with approval info"""
        obj = await self.get_object(id)
        current_user = request.state.user
        
        # Build response with approval info
        response = self._to_read_schema(obj)
        
        # ✅ Add approved_by field based on customer type
        if obj.customer_type == CustomerTypeEnum.BROKING:
            # Broking: Check if current user created this customer
            if current_user.id == obj.created_by:
                response_dict = response.dict()
                response_dict["approved_by"] = "me"
                return ReadSchema(**response_dict)
            else:
                response_dict = response.dict()
                response_dict["approved_by"] = "not me"
                return ReadSchema(**response_dict)
        
        elif obj.customer_type == CustomerTypeEnum.BOOKING:
            # Booking: Always management approval
            response_dict = response.dict()
            response_dict["approved_by"] = "management"
            return ReadSchema(**response_dict)
        
        return response

    async def check_duplicate_email(self, email: str, user_id: Optional[UUID] = None) -> bool:
        """
        Check if email already exists in User model.
        
        Args:
            email: Email to check
            user_id: Optional user ID to exclude from check (for updates)
        
        Returns:
            True if email exists, False otherwise
        """
        query = select(User).where(User.email == email)
        if user_id:
            query = query.where(User.id != user_id)
        
        existing_user = (await self.session.execute(query)).scalars().first()
        return existing_user is not None
    async def create(
        self,
        request: Request,
        item_data: Dict[str, Any],
        gst_document: UploadFile,
        pan_document: UploadFile,
        address_document: UploadFile,
    ) -> ReadSchema:
        try:
            email = item_data.get("email")
            if email:
                email_exists = await self.check_duplicate_email(email)
                if email_exists:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already taken. Please use a different email address."
                    )
            last_customer = (await self.session.execute(select(Customer).order_by(Customer.customer_code.desc()))).scalars().first()
            new_code = f"CUS{int(last_customer.customer_code.replace('CUS', '')) + 1:03d}" if last_customer and last_customer.customer_code else "CUS001"

            customer_data = item_data.copy()
           
            
            user_password = customer_data.get("password") 
            # Auto-approve Broking customers
            if customer_data.get("customer_type") == CustomerTypeEnum.BROKING:
                customer_data["status"] = CustomerStatusEnum.APPROVED

            upload_dir = "uploads/customer_documents"

            customer_data["gst_document"] = save_upload_file(gst_document, upload_dir)
            customer_data["pan_document"] = save_upload_file(pan_document, upload_dir)
            customer_data["address_document"] = save_upload_file(address_document, upload_dir)

            contact_persons_data = customer_data.pop("contact_persons", [])
            agreements_data = customer_data.pop("agreements", [])

            customer = Customer(**customer_data, customer_code=new_code, created_by=request.state.user.id, updated_by=request.state.user.id)

            if contact_persons_data:
                for cp_data in contact_persons_data:
                    contact_person = CustomerContactPerson(**cp_data)
                    customer.contact_persons.append(contact_person)

            if agreements_data:
                for ag_data in agreements_data:
                    agreement = CustomerAgreement(**ag_data)
                    customer.agreements.append(agreement)

            self.session.add(customer)
            await self.session.flush()

            # Create user for Approved customers (Broking)
           # ✅ Create user for Approved customers using model fields
            if customer.status == CustomerStatusEnum.APPROVED:
                customer_role = (await self.session.execute(select(Role).where(Role.name == "Customer"))).scalars().first()
                if not customer_role:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Customer role not found")

                user = User(
                    username=customer.customer_name,
                    email=customer.email if customer.email else f"{customer.customer_code.lower()}@example.com",
                    mobile=customer.mobile,  # ✅ From model
                    hashed_password=self.hash_password(user_password),  # ✅ Hash the password
                    role_id=customer_role.id,
                    first_name=customer.customer_name,
                )
                self.session.add(user)
                await self.session.flush()
                customer.user_id = user.id
                self.session.add(customer)

            await self.session.commit()
            await self.session.refresh(customer)

            # Explicit reload with eager loading to avoid lazy loading in async context
            query = (
                select(Customer)
                .options(
                    selectinload(Customer.vehicle_type),
                    selectinload(Customer.contact_persons),
                    selectinload(Customer.agreements),
                    selectinload(Customer.origin),
                    selectinload(Customer.destination),
                    selectinload(Customer.country),
                    selectinload(Customer.state),
                    selectinload(Customer.district),
                    selectinload(Customer.city),
                )
                .where(Customer.id == customer.id)
            )
            result = await self.session.execute(query)
            customer = result.scalars().first()

            return self._to_read_schema(customer)

        except IntegrityError as e:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Data integrity error: {e.orig}")
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {e}")


    async def delete(self, request: Request, id: UUID):
        try:
            # with self.session.begin_nested():
            customer = await self.get_object(id)
            
            user = (await self.session.execute(select(User).where(User.id == customer.user_id))).scalars().first()
            if user:
                await self.session.delete(user)

            await self.session.delete(customer)
            await self.session.commit()
            return {"detail": OBJECT_DELETED}
        except Exception as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {e}")

    async def update_status(self, request: Request, id: UUID, new_status: CustomerStatusEnum, reject_reason: Optional[str] = None) -> ReadSchema:
        try:
            customer = await self.get_object(id)
            current_user = request.state.user
            
            if new_status == CustomerStatusEnum.APPROVED:
                if customer.customer_type == CustomerTypeEnum.BROKING:
                    if current_user.id != customer.created_by:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only the creator can approve Broking customers"
                        )
                
                elif customer.customer_type == CustomerTypeEnum.BOOKING:
                    if not current_user.role or current_user.role.name.lower() not in ["management", "admin"]:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only Management can approve Booking customers"
                        )
                
               
            
            # Validate reject_reason if status is REJECTED
            if new_status == CustomerStatusEnum.REJECTED:
                if not reject_reason or reject_reason.strip() == "":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Reject reason is required when status is REJECTED"
                    )
                customer.reject_reason = reject_reason
            else:
                customer.reject_reason = None
            
            customer.status = new_status
            customer.updated_by = request.state.user.id
            customer.updated_at = datetime.utcnow()

            if new_status == CustomerStatusEnum.APPROVED:
                customer_role = (await self.session.execute(select(Role).where(Role.name == "Customer"))).scalars().first()
                if not customer_role:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Customer role not found")

                # ✅ Use customer's stored credentials
                user = User(
                    username=customer.customer_name,
                    email=customer.email if customer.email else f"{customer.customer_code.lower()}@example.com",
                    mobile=customer.mobile,  
                    hashed_password=self.hash_password(customer.password),  
                    role_id=customer_role.id,
                    first_name=customer.customer_name,
                )
                self.session.add(user)
                await self.session.flush()
                customer.user_id = user.id

            self.session.add(customer)

            await self.session.commit()
            await self.session.refresh(customer)
            
            customer = await self.get_object(customer.id)
            return self._to_read_schema(customer)
        
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {e}")



    async def update(
        self,
        request: Request,
        id: UUID,
        item_data: CustomerUpdate,
        gst_document: Optional[UploadFile] = None,
        pan_document: Optional[UploadFile] = None,
        address_document: Optional[UploadFile] = None,
        agreement_documents: Optional[UploadFile] = None,
    ) -> ReadSchema:
        try:
            # with self.session.begin_nested():
            customer = await self.get_object(id)
            update_data = item_data.dict(exclude_unset=True)
            new_email = update_data.get("email")
            if new_email and new_email != customer.email:
                email_exists = await self.check_duplicate_email(new_email, customer_id=id)
                if email_exists:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already taken. Please use a different email address."
                    )
            upload_dir = "uploads/customer_documents"
            if gst_document:
                update_data["gst_document"] = save_upload_file(gst_document, upload_dir)
            if pan_document:
                update_data["pan_document"] = save_upload_file(pan_document, upload_dir)
            if address_document:
                update_data["address_document"] = save_upload_file(address_document, upload_dir)

            contact_persons_data = update_data.pop("contact_persons", None)
            agreements_data = update_data.pop("agreements", None)
            
            for key, value in update_data.items():
                setattr(customer, key, value)

            customer.updated_by = request.state.user.id
            customer.updated_at = datetime.utcnow()

            if contact_persons_data is not None:
                customer.contact_persons.clear()
                for cp_data in contact_persons_data:
                    customer.contact_persons.append(CustomerContactPerson(**cp_data))

                # ✅ Smart Agreements Update (NEW)
            if agreements_data is not None:
                agreement_docs = agreement_documents if agreement_documents else []
                
                # Get existing agreements mapped by ID
                existing_agreements = {str(ag.id): ag for ag in customer.agreements}
                updated_agreement_ids = set()
                
                for idx, ag_data in enumerate(agreements_data):
                    agreement_id = ag_data.get('id')
                    
                    if agreement_id and str(agreement_id) in existing_agreements:
                        # ✅ UPDATE EXISTING AGREEMENT
                        existing_agreement = existing_agreements[str(agreement_id)]
                        existing_agreement.start_date = ag_data['start_date']
                        existing_agreement.end_date = ag_data['end_date']
                        
                        # Update document if provided
                        if idx < len(agreement_docs) and agreement_docs[idx]:
                            doc_path = save_upload_file(
                                agreement_docs[idx], 
                                "uploads/customer_agreement_documents"
                            )
                            existing_agreement.agreement_document = doc_path
                        # else: Keep existing document
                        
                        updated_agreement_ids.add(str(agreement_id))
                        self.session.add(existing_agreement)
                    else:
                        # ✅ CREATE NEW AGREEMENT
                        if idx >= len(agreement_docs) or not agreement_docs[idx]:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"New agreement at index {idx} requires an agreement document"
                            )
                        
                        doc_path = save_upload_file(
                            agreement_docs[idx], 
                            "uploads/customer_agreement_documents"
                        )
                        
                        new_agreement = CustomerAgreement(
                            customer_id=customer.id,
                            start_date=ag_data['start_date'],
                            end_date=ag_data['end_date'],
                            agreement_document=doc_path
                        )
                        self.session.add(new_agreement)
                
                # ✅ DELETE AGREEMENTS NOT IN UPDATE LIST
                for ag_id, agreement in existing_agreements.items():
                    if ag_id not in updated_agreement_ids:
                        await self.session.delete(agreement)
                self.session.add(customer)
                await self.session.flush()

            await self.session.commit()
            await self.session.refresh(customer)
            return self._to_read_schema(customer)
        except IntegrityError as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Data integrity error: {e.orig}")
        except Exception as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {e}")
        
    async def check_duplicate(self, gst_number: Optional[str] = None, pan_number: Optional[str] = None, customer_id: Optional[UUID] = None) -> dict:
        """
        Check if GST number or PAN number already exists for another vendor.
        
        Args:
            gst_number: GST number to check
            pan_number: PAN number to check
            customer_id: Optional vendor ID to exclude from check (for updates)
        
        Returns:
            Dict with duplicate status and existing vendor details if found
        """
        result = {
            "gst_duplicate": False,
            "pan_duplicate": False,
            "gst_customer": None,
            "pan_customer": None,
        }
        
        # Check GST number
        if gst_number:
            query = select(Customer).where(Customer.gst_number == gst_number)
            if customer_id:
                query = query.where(Customer.id != customer_id)
            
            existing_customer = (await self.session.execute(query)).scalars().first()
            if existing_customer:
                result["gst_duplicate"] = True
                result["gst_customer"] = {
                    "id": str(existing_customer.id),
                    "customer_code": existing_customer.customer_code,
                    "customer_name": existing_customer.customer_name,
                    "gst_number": existing_customer.gst_number,
                }
        
        # Check PAN number
        if pan_number:
            query = select(Customer).where(Customer.pan_number == pan_number)
            if customer_id:
                query = query.where(Customer.id != customer_id)
            
            existing_customer = (await self.session.execute(query)).scalars().first()
            if existing_customer:
                result["pan_duplicate"] = True
                result["pan_customer"] = {
                    "id": str(existing_customer.id),
                    "customer_code": existing_customer.customer_code,
                    "customer_name": existing_customer.customer_name,
                    "pan_number": existing_customer.pan_number,
                }
        
        return result

    async def list_approved(
            self, 
            search: Optional[str] = None,
            status: CustomerStatusEnum | None = None
        ) -> ApprovedCustomerList:
        """
        List all approved customers without pagination, with search functionality.

        Args:
            search: Optional search string for customer name, code, GST, or PAN.

        Returns:
            A list of approved customers matching the search criteria.
        """

        # Start with a base statement
        statement = select(Customer)

        # Apply eager loading for related address fields
        statement = statement.options(
                selectinload(Customer.country),
                selectinload(Customer.state),
                selectinload(Customer.district),
                selectinload(Customer.city),
            )

        # Filter by status: use provided status or default to APPROVED
        if status:
            statement = statement.where(Customer.status == status)
        # else:
        #     statement = statement.where(Customer.status == CustomerStatusEnum.APPROVED)

        if search:
            search_term = f"%{search}%"
            statement = statement.where(
                (Customer.customer_name.ilike(search_term)) |
                (Customer.customer_code.ilike(search_term)) |
                (Customer.gst_number == search) |
                (Customer.pan_number == search)
            )

        customers = (await self.session.execute(statement.order_by(Customer.created_at.desc()))).scalars().all()

        return ApprovedCustomerList(
            results=[
                ApprovedCustomerRead(
                    id=c.id,
                    name=c.customer_name,
                    code=c.customer_code,
                    address=c.address,
                    type=c.customer_type,
                    mobile=c.mobile,  # ✅ ADDED
                    email=c.email,  
                    created_at=c.created_at,
                    status=c.status
                )
                for c in customers
                ]
        )

    async def check_email_availability(self, email: str) -> dict:
        """
        Check if email is available (not taken).
        
        Args:
            email: Email to check
        
        Returns:
            Dict with availability status
        """
        query = select(User).where(User.email == email)
        existing_user = (await self.session.execute(query)).scalars().first()
        
        return {
            "email": email,
            "is_available": existing_user is None,
            "is_taken": existing_user is not None
        }
