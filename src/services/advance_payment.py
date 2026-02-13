from uuid import UUID
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func, or_, and_

from core import messages
from models.advance_payment import AdvancePayment as Model
from models import Customer, Vendor, Trip, TripVendor, PaymentApprovalHistory
from models.enums import TimePeriodEnum
from models.customer import CustomerTypeEnum
from models.trip import TripStatusEnum, TripStatusHistory
from schemas.advance_payment import (
    AdvancePaymentList as ListSchema,
    AdvancePaymentRead as ReadSchema,
    AdvancePaymentCreate as CreateSchema,
    AdvancePaymentTripRead,
    AdvancePaymentTripList,
    AdvancePaymentUpdate as UpdateSchema,
)
from schemas.branch import IdName
from utils.date_helpers import get_date_range


OBJECT_NOT_FOUND = "Advance payment not found"
OBJECT_EXIST = "Advance payment already exists"
OBJECT_DELETED = "Advance payment deleted successfully"


class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_object(self, id: UUID) -> Model:
        """Get advance payment by ID with relationships loaded"""
        stmt = (
            select(Model)
            .options(
                selectinload(Model.customer),
                selectinload(Model.vendor),
                selectinload(Model.trip).selectinload(Trip.assigned_vendor),
                selectinload(Model.trip).selectinload(Trip.status_history), 
            )
            .where(Model.id == id)
        )
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=OBJECT_NOT_FOUND
            )
        return obj

    async def _to_read_schema(self, obj: Model) -> ReadSchema:
        """Convert model to read schema"""
        from schemas.advance_payment import TripDetails

        if obj.payment_type == "Advance Payment" and obj.trip.is_advance_given:
            action_required = False
        elif obj.payment_type == "Balance Payment":
            stmt = select(Model).where(Model.trip_id == obj.trip_id)
            result = await self.session.execute(stmt)
            previous_payments = result.scalars().all()

            total_paid_amount = sum(payment.amount for payment in previous_payments if payment.amount and payment.is_paid_amount is True)

            if obj.trip.assigned_vendor:
                total_balance = (obj.trip.assigned_vendor.trip_rate or Decimal("0.0")) + (obj.trip.assigned_vendor.other_unloading_charges or Decimal("0.0")) + (obj.trip.assigned_vendor.other_charges or Decimal("0.0")) - (obj.trip.deducted_amount or Decimal("0.0")) - (obj.trip.pod_penalty_amount or Decimal("0.0"))
            else:
                total_balance = Decimal("0.0")

            action_required = total_paid_amount < total_balance
        elif obj.payment_type == "Deducted Amount":
            obj.is_paid_amount = True
            action_required = False
        else:
            action_required = False
        
        return ReadSchema(
            id=obj.id,
            payment_date=obj.payment_date,
            utr_no=obj.utr_no,
            amount=obj.amount,
            payment_type=obj.payment_type,
            action_required=action_required,
            is_paid_amount=obj.is_paid_amount,
            is_payment_due=obj.is_payment_due,
            created_at=obj.created_at,
        )

    async def _paginate(self, base_stmt, request: Request, page=1, size=10, trip_id: UUID | None = None, for_customer: bool = False) -> ListSchema:
        """Paginate query results"""
        # Calculate total count
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar()

        offset = (page - 1) * size
        
        # Add options and pagination - ✅ Fixed: Load status_history for pod_penalty_amount property
        stmt = (
            base_stmt
            .options(
                selectinload(Model.customer),
                selectinload(Model.vendor),
                selectinload(Model.trip).selectinload(Trip.assigned_vendor),
                selectinload(Model.trip).selectinload(Trip.status_history),  
            )
            .order_by(Model.created_at.asc())
            .offset(offset)
            .limit(size)
        )
        
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

        converted_results = [await self._to_read_schema(obj) for obj in results]

        paid_amount = sum(payment.amount for payment in results if payment.amount and payment.is_paid_amount is True and payment.is_deduct_amount is False)
        balance_amount = Decimal("0.0")
        remaining_amount = Decimal("0.0")

        if trip_id and results:
            trip = results[0].trip
        
            if for_customer:
                balance_amount = ((trip.trip_rate or Decimal("0.0")) + (trip.loading_unloading_charges or Decimal("0.0")))
                remaining_amount = balance_amount - paid_amount
            elif trip and trip.assigned_vendor:
                balance_amount = ((trip.assigned_vendor.trip_rate or Decimal("0.0")) + (trip.assigned_vendor.other_unloading_charges or Decimal("0.0")) + (trip.assigned_vendor.other_charges or Decimal("0.0"))) - ((trip.deducted_amount or Decimal("0.0")) + (trip.pod_penalty_amount or Decimal("0.0")))
                remaining_amount = balance_amount - paid_amount 

        elif trip_id and not results:
            # ✅ Fixed: Load status_history for pod_penalty_amount property
            trip_stmt = (
                select(Trip)
                .options(
                    selectinload(Trip.assigned_vendor),
                    selectinload(Trip.status_history),  
                )
                .where(Trip.id == trip_id)
            )
            trip_result = await self.session.execute(trip_stmt)
            trip = trip_result.scalars().first()
            
            if for_customer and trip:
                balance_amount = ((trip.trip_rate or Decimal("0.0")) + (trip.loading_unloading_charges or Decimal("0.0")))
                remaining_amount = balance_amount
            elif trip and trip.assigned_vendor:
                balance_amount = (trip.assigned_vendor.trip_rate or Decimal("0.0")) + (trip.assigned_vendor.other_unloading_charges or Decimal("0.0")) + (trip.assigned_vendor.other_charges or Decimal("0.0")) - (trip.deducted_amount or Decimal("0.0")) - (trip.pod_penalty_amount or Decimal("0.0"))
                remaining_amount = balance_amount

        return ListSchema(
            total=total, 
            next=next_url, 
            previous=previous_url, 
            paid_amount=paid_amount, 
            balance_amount=balance_amount, 
            remaining_amount=remaining_amount, 
            results=converted_results
        )

    async def list(
        self,
        request: Request,
        page: int = 1,
        size: int = 10,
        customer_id: UUID | None = None,
        vendor_id: UUID | None = None,
        trip_id: UUID | None = None,
        time_period: TimePeriodEnum | None = None, 
        start_date: date | None = None, 
        end_date: date | None = None, 
    ) -> ListSchema:
        """List advance payments with optional filters"""
        stmt = select(Model)

        for_customer = False
        
        date_start, date_end = get_date_range(time_period, start_date, end_date)
        if trip_id:
            stmt = stmt.where(Model.trip_id == trip_id)
        if customer_id:
            stmt = stmt.where(Model.customer_id == customer_id)
            for_customer = True
        if vendor_id:
            stmt = stmt.where(Model.vendor_id == vendor_id)
        if date_start:
            stmt = stmt.where(Model.created_at >= date_start)
        if date_end:
            stmt = stmt.where(Model.created_at <= date_end)

        return await self._paginate(stmt, request, page, size, trip_id=trip_id, for_customer=for_customer)

    async def read(self, id: UUID) -> ReadSchema:
        """Get single advance payment by ID"""
        obj = await self.get_object(id)
        return await self._to_read_schema(obj)

    async def create(self, request: Request, item: CreateSchema) -> ReadSchema:
        """Create new advance payment"""
        try:
            user = request.state.user
            payment_for_customer = item.payment_for_customer
            
            # Validate trip exists - ✅ Fixed: Load status_history for pod_penalty_amount
            stmt = (
                select(Trip)
                .options(
                    selectinload(Trip.assigned_vendor).selectinload(TripVendor.vendor),
                    selectinload(Trip.customer),
                    selectinload(Trip.status_history),  # ✅ Added
                )
                .where(Trip.id == item.trip_id)
            )
            trip_result = await self.session.execute(stmt)
            trip = trip_result.scalars().first()
            
            if not trip:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Trip with id {item.trip_id} not found"
                )
            
            if payment_for_customer:
                if not trip.customer:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found for this trip.")
                
                customer_total_balance = (trip.trip_rate or Decimal("0.0")) + (trip.loading_unloading_charges or Decimal("0.0"))
                
                prev_stmt = select(Model).where(
                    Model.trip_id == item.trip_id,
                    Model.customer_id == trip.customer_id,
                    Model.is_paid_amount == True,
                    Model.is_deduct_amount == False
                )
                prev_result = await self.session.execute(prev_stmt)
                previous_payments = prev_result.scalars().all()
                
                total_paid_to_customer = sum(payment.amount for payment in previous_payments if payment.amount)
                
                if (total_paid_to_customer + item.amount) > customer_total_balance:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Payment amount exceeds the total customer bill of {customer_total_balance}. Already paid: {total_paid_to_customer}"
                    )
                
                advance_payment_data = item.dict()
                advance_payment_data['customer_id'] = trip.customer_id
                obj = Model(**advance_payment_data, is_paid_amount=True, created_by=user.id, updated_by=user.id)
                if not obj.payment_type:
                    obj.payment_type = "Customer Payment"
                
                # Calculate customer remaining amount
                customer_remaining = customer_total_balance - (total_paid_to_customer + item.amount)
                
                # Calculate vendor remaining amount
                vendor_remaining = Decimal("0.0")
                if trip.assigned_vendor:
                    vendor_total_balance = (trip.assigned_vendor.trip_rate or Decimal("0.0")) + (trip.assigned_vendor.other_unloading_charges or Decimal("0.0")) + (trip.assigned_vendor.other_charges or Decimal("0.0")) - (trip.deducted_amount or Decimal("0.0")) - (trip.pod_penalty_amount or Decimal("0.0"))
                    
                    vendor_stmt = select(Model).where(Model.trip_id == trip.id, Model.vendor_id == trip.assigned_vendor.vendor.id, Model.is_paid_amount == True)
                    vendor_result = await self.session.execute(vendor_stmt)
                    vendor_payments = vendor_result.scalars().all()
                    total_paid_to_vendor = sum(payment.amount for payment in vendor_payments if payment.amount)
                    vendor_remaining = vendor_total_balance - total_paid_to_vendor
                
                # If both vendor and customer remaining are zero, create status history
                if vendor_remaining <= 0 and customer_remaining <= 0:
                    previous_status = trip.status
                    trip.status = TripStatusEnum.COMPLETED
                    trip.updated_by = user.id
                    trip.updated_at = datetime.utcnow()
                    
                    history_entry = TripStatusHistory(
                        trip_id=trip.id,
                        previous_status=previous_status,
                        current_status=TripStatusEnum.COMPLETED,
                        remarks="Trip completed.",
                        updated_by=user.id
                    )
                    self.session.add(history_entry)

            else: # Payment for Vendor
                if not trip.is_advance_payment_done:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Advance payment approve required for this trip."
                    )
            
                # Check if advance payment is already done
                if trip.is_advance_payment_done and trip.is_advance_given and not trip.is_balance_payment_approve:
                    # If POD not submitted yet, balance approval is required
                    if trip.status == TripStatusEnum.POD_SUBMITTED:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Balance payment approve required for this trip."
                        )
                    # If POD submitted or beyond, advance payment is already done
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Advance Payment already done."
                        )
            
                # fetch vendor based on trip id
                if not trip.assigned_vendor:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Trip has no assigned vendor. Cannot process advance payment."
                    )
                
                vendor = trip.assigned_vendor.vendor

                if not vendor:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Vendor not found for this trip."
                    )

                # Create a dictionary from the Pydantic model and add the IDs
                advance_payment_data = item.dict()
                advance_payment_data['vendor_id'] = vendor.id
            
                # Fetch previous advance payments for this trip
                prev_stmt = select(Model).where(Model.trip_id == item.trip_id)
                prev_result = await self.session.execute(prev_stmt)
                previous_payments = prev_result.scalars().all()
                
                total_paid_amount = sum(payment.amount for payment in previous_payments if payment.amount and payment.is_paid_amount is True)

                # Add the current payment amount
                total_paid_amount += item.amount

                # Get the required advance amount from the trip's assigned vendor
                required_advance = trip.assigned_vendor.advance
                total_balance = (trip.assigned_vendor.trip_rate or Decimal("0.0")) + (trip.assigned_vendor.other_unloading_charges or Decimal("0.0")) + (trip.assigned_vendor.other_charges or Decimal("0.0")) - (trip.deducted_amount or Decimal("0.0")) - (trip.pod_penalty_amount or Decimal("0.0"))
                
                # Create the advance payment object initially
                obj = Model(
                    **advance_payment_data,
                    is_paid_amount=True,
                    created_by=user.id,
                    updated_by=user.id
                )

                # If total paid amount meets or exceeds the required advance, update trip status
                if total_paid_amount >= required_advance and not trip.is_advance_given and not trip.is_balance_payment_approve:
                    if total_paid_amount > required_advance:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Advance payment should not exceed the required advance amount {required_advance}."
                        )

                    obj.payment_type = "Advance Payment"
                    previous_status = trip.status
                    trip.is_advance_given = True
                    trip.status = TripStatusEnum.ADVANCE_PAYMENT
                    trip.updated_by = user.id
                    trip.updated_at = datetime.utcnow()

                    # Create a history entry for the status change
                    history_entry = TripStatusHistory(
                        trip_id=trip.id,
                        previous_status=previous_status,
                        current_status=TripStatusEnum.ADVANCE_PAYMENT,
                        remarks="Total advance payment completed.",
                        updated_by=user.id
                    )
                    self.session.add(history_entry)
                elif total_paid_amount >= total_balance and trip.is_advance_given and trip.is_balance_payment_approve:
                    if total_paid_amount > total_balance:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Balance payment should not exceed the required amount."
                        )
                    
                    # Calculate vendor and customer remaining amounts
                    vendor_remaining = total_balance - total_paid_amount
                    
                    # Fetch customer payments to calculate customer remaining
                    customer_remaining = Decimal("0.0")
                    if trip.customer:
                        customer_total_balance = (trip.trip_rate or Decimal("0.0")) + (trip.loading_unloading_charges or Decimal("0.0"))
                        
                        cust_stmt = select(Model).where(
                            Model.trip_id == trip.id,
                            Model.customer_id == trip.customer_id,
                            Model.is_paid_amount == True,
                            Model.is_deduct_amount == False
                        )
                        cust_result = await self.session.execute(cust_stmt)
                        customer_payments = cust_result.scalars().all()
                        total_paid_to_customer = sum(payment.amount for payment in customer_payments if payment.amount)
                        customer_remaining = customer_total_balance - total_paid_to_customer
                    
                    obj.payment_type = "Balance Payment"
                    previous_status = trip.status
                    trip.is_advance_given = True
                    trip.updated_by = user.id
                    trip.updated_at = datetime.utcnow()

                    # Check if both vendor and customer remaining amounts are zero
                    # Check customer type for status determination
                    if trip.customer and trip.customer.customer_type == CustomerTypeEnum.BOOKING:
                        if vendor_remaining <= 0:
                            trip.status = TripStatusEnum.COMPLETED
                            status_remarks = "Trip completed."
                        else:
                            trip.status = TripStatusEnum.IN_TRANSIT
                            status_remarks = "In Transit"
                    else:
                        # For non-booking customers, check both vendor and customer remaining amounts
                        if vendor_remaining <= 0 and customer_remaining <= 0:
                            trip.status = TripStatusEnum.IN_TRANSIT
                            status_remarks = "In Transit"
                        else:
                            trip.status = TripStatusEnum.IN_TRANSIT
                            status_remarks = "In Transit"

                    # Create a history entry for the status change
                    history_entry = TripStatusHistory(
                        trip_id=trip.id,
                        previous_status=previous_status,
                        current_status=trip.status,
                        remarks=status_remarks,
                        updated_by=user.id
                    )
                    self.session.add(history_entry)
                else:
                    obj.payment_type = "Advance Payment" if not trip.is_advance_given else "Balance Payment"

            self.session.add(obj)
            await self.session.commit()
            await self.session.refresh(obj)
            
            return await self.read(obj.id)
        except IntegrityError as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Data integrity error: {e.orig}"
            )
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {e}"
            )

    async def update(self, request: Request, id: UUID, item: UpdateSchema) -> ReadSchema:
        """Update existing advance payment"""
        try:
            user = request.state.user
            obj = await self.get_object(id)

            # Fetch previous payments for this trip
            prev_stmt = select(Model).where(Model.trip_id == obj.trip_id, Model.id != id)
            
            # If payment_for_customer is True, only fetch customer transactions
            if item.payment_for_customer:
                prev_stmt = prev_stmt.where(Model.customer_id.isnot(None))

                prev_result = await self.session.execute(prev_stmt)
                previous_payments = prev_result.scalars().all()

                # Validate trip exists - ✅ Fixed: Load status_history for pod_penalty_amount
                trip_stmt = (
                    select(Trip)
                    .options(
                        selectinload(Trip.status_history),  # ✅ Added
                    )
                    .where(Trip.id == obj.trip_id)
                )
                trip_result = await self.session.execute(trip_stmt)
                trip = trip_result.scalars().first()
                
                if not trip:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Trip with id {obj.trip_id} not found"
                    )

                total_paid_amount = sum(payment.amount for payment in previous_payments if payment.amount and payment.is_paid_amount is True)

                # Add the current payment amount
                total_paid_amount += item.amount
                required_advance = 0
                total_balance = (trip.trip_rate or Decimal("0.0")) + (trip.loading_unloading_charges or Decimal("0.0"))
            else:
                prev_stmt = prev_stmt.where(Model.vendor_id.isnot(None))
                
                prev_result = await self.session.execute(prev_stmt)
                previous_payments = prev_result.scalars().all()

                # Validate trip exists - ✅ Fixed: Load status_history for pod_penalty_amount
                trip_stmt = (
                    select(Trip)
                    .options(
                        selectinload(Trip.assigned_vendor),
                        selectinload(Trip.status_history),  # ✅ Added
                    )
                    .where(Trip.id == obj.trip_id)
                )
                trip_result = await self.session.execute(trip_stmt)
                trip = trip_result.scalars().first()
                
                if not trip:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Trip with id {obj.trip_id} not found"
                    )

                total_paid_amount = sum(payment.amount for payment in previous_payments if payment.amount and payment.is_paid_amount is True)

                # Add the current payment amount
                total_paid_amount += item.amount

                if not trip.assigned_vendor:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Trip has no assigned vendor."
                    )

                required_advance = trip.assigned_vendor.advance
                total_balance = (trip.assigned_vendor.trip_rate or Decimal("0.0")) + (trip.assigned_vendor.other_unloading_charges or Decimal("0.0")) + (trip.assigned_vendor.other_charges or Decimal("0.0")) - (trip.deducted_amount or Decimal("0.0")) - (trip.pod_penalty_amount or Decimal("0.0"))

            print("Total Paid Amount:", total_paid_amount)
            print("Required Advance:", required_advance)
            print("Total Balance:", total_balance)
            print("Advance Payment:", item.payment_for_customer)

            # If total paid amount meets or exceeds the required advance, update trip status
            if total_paid_amount >= required_advance and not trip.is_advance_given and not trip.is_balance_payment_approve:
                if total_paid_amount > required_advance:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Advance payment should not exceed the required advance amount {required_advance}."
                    )
            elif total_paid_amount >= total_balance and trip.is_advance_given and trip.is_balance_payment_approve:
                if total_paid_amount > total_balance:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Balance payment should not exceed the required amount."
                    )

            # Update fields
            update_data = item.dict(exclude_unset=True)
            # Remove payment_for_customer as it's not a model field
            update_data.pop('payment_for_customer', None)
            for key, value in update_data.items():
                setattr(obj, key, value)

            obj.updated_by = user.id
            obj.updated_at = datetime.utcnow()

            self.session.add(obj)
            await self.session.commit()
            await self.session.refresh(obj)
            
            return await self.read(obj.id)

        except IntegrityError as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Data integrity error: {e.orig}"
            )
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {e}"
            )

    async def delete(self, request: Request, id: UUID):
        """Delete advance payment"""
        try:
            obj = await self.get_object(id)
            await self.session.delete(obj)
            await self.session.commit()
            return {"detail": OBJECT_DELETED}
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {e}"
            )
        
    async def advance_payment_approved_pending_trips(
            self,
            request: Request,
            page: int = 1,
            size: int = 10,
            search: str | None = None,
        ) -> AdvancePaymentTripList:
        """List trips with status VEHICLE_LOADED for advance payment."""
        stmt = (
            select(Trip)
            .options(
                selectinload(Trip.assigned_vendor).selectinload(TripVendor.vendor),
                selectinload(Trip.customer),
                selectinload(Trip.status_history),  # ✅ Added
            )
            .join(Trip.assigned_vendor)
            .join(TripVendor.vendor)
            .join(Trip.customer)
            .where(
                or_(
                    Trip.status == TripStatusEnum.VEHICLE_LOADED,
                    Trip.status == TripStatusEnum.POD_SUBMITTED
                )
            )
            .where(
                or_(
                    Trip.is_advance_payment_done == False,
                    and_(Trip.is_advance_given == True, Trip.is_balance_payment_approve == False)
                )
            )
        )

        if search:
            stmt = stmt.where(
                (Trip.trip_code.ilike(f"%{search}%")) |
                (Customer.customer_name.ilike(f"%{search}%")) |
                (Vendor.vendor_name.ilike(f"%{search}%"))
            )

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar()

        offset = (page - 1) * size
        
        stmt = stmt.order_by(Trip.trip_date.desc()).offset(offset).limit(size)
        result = await self.session.execute(stmt)
        results = result.scalars().all()

        next_url = str(request.url.include_query_params(page=page + 1)) if offset + size < total else None
        previous_url = str(request.url.include_query_params(page=page - 1)) if page > 1 else None

        converted_results = []
        for trip in results:
            if trip.assigned_vendor:
                # Calculate paid amount for this trip (same logic as _paginate)
                stmt_payments = select(Model).where(Model.trip_id == trip.id)
                payments_result = await self.session.execute(stmt_payments)
                previous_payments = payments_result.scalars().all()
                
                paid_amount = sum(payment.amount for payment in previous_payments if payment.amount and payment.is_paid_amount is True)
                
                # Calculate balance amount (same logic as _paginate)
                balance_amount = (
                    (trip.assigned_vendor.trip_rate or Decimal("0.0")) + 
                    (trip.assigned_vendor.other_unloading_charges or Decimal("0.0")) + 
                    (trip.assigned_vendor.other_charges or Decimal("0.0")) - 
                    (trip.deducted_amount or Decimal("0.0")) - 
                    (trip.pod_penalty_amount or Decimal("0.0"))
                )
                
                # Calculate remaining amount
                remaining_amount = balance_amount - paid_amount
                
                converted_results.append(AdvancePaymentTripRead(
                    trip_id=trip.id,
                    type=trip.payment_type,
                    customer_name=trip.customer.customer_name,
                    customer_code=trip.customer.customer_code,
                    trip_code=trip.trip_code,
                    trip_date=trip.trip_date,
                    vendor_id=trip.assigned_vendor.vendor.id,
                    vendor_code=trip.assigned_vendor.vendor.vendor_code,
                    vendor_name=trip.assigned_vendor.vendor.vendor_name,
                    trip_rate=trip.assigned_vendor.trip_rate + trip.assigned_vendor.other_charges,
                    advance=trip.assigned_vendor.advance,
                    remaining=remaining_amount,
                ))

        return AdvancePaymentTripList(total=total, next=next_url, previous=previous_url, results=converted_results)

    async def approve_trip_advance_payment(self, request: Request, trip_id: UUID):
        """Approve advance payment for a trip."""
        try:
            user = request.state.user
            stmt = select(Trip).options(selectinload(Trip.assigned_vendor).selectinload(TripVendor.vendor)).where(Trip.id == trip_id)
            result = await self.session.execute(stmt)
            trip = result.scalars().first()
            
            if not trip:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Trip with id {trip_id} not found"
                )

            if not trip.assigned_vendor:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No vendor has been assigned to this trip."
                )

            # Update trip fields
            trip.is_advance_payment_done = True

            # Create history record
            history_entry = PaymentApprovalHistory(
                trip_id=trip_id,
                approval_type="Advance",
                approved_by=user.id,
                remarks="Advance payment approved",
                created_by=user.id,
                updated_by=user.id
            )

            # Create AdvancePayment history record
            # advance_entry = Model(
            #     trip_id=trip_id,
            #     vendor_id=trip.assigned_vendor.vendor.id,
            #     payment_type="Advance Payment",
            #     amount=trip.assigned_vendor.advance,
            #     is_paid_amount=False,
            #     is_deduct_amount=False,
            #     is_payment_due=True,
            #     created_by=user.id,
            #     created_at=datetime.utcnow()

            # )
            
            self.session.add(trip)
            self.session.add(history_entry)
            # self.session.add(advance_entry)

            await self.session.commit()
            await self.session.refresh(trip)
            # await self.session.refresh(advance_entry)

            return {"detail": "Trip advance payment approved successfully"}
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {e}"
            )
        
    async def approve_trip_balance_payment(self, request: Request, trip_id: UUID):
        """Approve balance payment for a trip."""
        try:
            user = request.state.user
            stmt = select(Trip).where(Trip.id == trip_id)
            result = await self.session.execute(stmt)
            trip = result.scalars().first()
            
            if not trip:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Trip with id {trip_id} not found"
                )
            
            if not trip.is_advance_given:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Advance payment required for this trip."
                )

            # Update trip fields
            trip.is_balance_payment_approve = True

            # Create history record
            history_entry = PaymentApprovalHistory(
                trip_id=trip_id,
                approval_type="Balance",
                approved_by=user.id,
                remarks="Balance payment approved",
                created_by=user.id,
                updated_by=user.id
            )

            self.session.add(trip)
            self.session.add(history_entry)
            await self.session.commit()
            await self.session.refresh(trip)

            return {"detail": "Trip balance payment approved successfully"}
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {e}"
            )

    async def list_payment_approval_history(
        self,
        request: Request,
        page: int = 1,
        size: int = 10,
        trip_id: UUID | None = None,
        approval_type: str | None = None,
        branch_id: UUID | None = None,
        time_period: TimePeriodEnum | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ):
        """List payment approval history with optional filters"""
        from models import User
        from schemas.payment_approval_history import PaymentApprovalHistoryRead, PaymentApprovalHistoryList
        
        stmt = (
            select(PaymentApprovalHistory)
            .options(
                selectinload(PaymentApprovalHistory.trip).selectinload(Trip.customer),
                selectinload(PaymentApprovalHistory.trip).selectinload(Trip.assigned_vendor).selectinload(TripVendor.vendor),
                selectinload(PaymentApprovalHistory.trip).selectinload(Trip.status_history),
                selectinload(PaymentApprovalHistory.approver),
            )
        )
        
        # Apply date range filter using get_date_range utility
        date_start, date_end = get_date_range(time_period, start_date, end_date)
        if date_start:
            stmt = stmt.where(PaymentApprovalHistory.created_at >= date_start)
        if date_end:
            stmt = stmt.where(PaymentApprovalHistory.created_at <= date_end)
        
        # Apply other filters
        if trip_id:
            stmt = stmt.where(PaymentApprovalHistory.trip_id == trip_id)
        if approval_type:
            stmt = stmt.where(PaymentApprovalHistory.approval_type == approval_type)
        if branch_id:
            # Join with Trip table to filter by branch
            stmt = stmt.join(PaymentApprovalHistory.trip).where(Trip.branch_id == branch_id)
        
        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar()
        
        # Pagination
        offset = (page - 1) * size
        stmt = stmt.order_by(PaymentApprovalHistory.created_at.desc()).offset(offset).limit(size)
        
        result = await self.session.execute(stmt)
        results = result.scalars().all()
        
        # Generate pagination URLs
        next_url = (
            str(request.url.include_query_params(page=page + 1))
            if offset + size < total else None
        )
        previous_url = (
            str(request.url.include_query_params(page=page - 1))
            if page > 1 else None
        )
        
        # ✅ Fetch all payments for all trips in results upfront (to avoid N+1 queries)
        trip_ids = [history.trip_id for history in results if history.trip_id]
        payments_by_trip = {}
        
        if trip_ids:
            stmt_payments = select(Model).where(Model.trip_id.in_(trip_ids))
            payments_result = await self.session.execute(stmt_payments)
            all_payments = payments_result.scalars().all()
            
            # Group payments by trip_id
            for payment in all_payments:
                if payment.trip_id not in payments_by_trip:
                    payments_by_trip[payment.trip_id] = []
                payments_by_trip[payment.trip_id].append(payment)
        
        # Convert to schema
        converted_results = []
        for history in results:
            # Build customer details object
            customer = None
            if history.trip and history.trip.customer:
                from schemas.payment_approval_history import CustomerDetails
                customer = CustomerDetails(
                    id=history.trip.customer.id,
                    name=history.trip.customer.customer_name,
                    code=history.trip.customer.customer_code
                )
            
            # Build vendor details object
            vendor = None
            if history.trip and history.trip.assigned_vendor and history.trip.assigned_vendor.vendor:
                from schemas.payment_approval_history import VendorDetails
                vendor = VendorDetails(
                    id=history.trip.assigned_vendor.vendor.id,
                    name=history.trip.assigned_vendor.vendor.vendor_name,
                    code=history.trip.assigned_vendor.vendor.vendor_code
                )
            
            # Calculate trip_rate and trip_remaining (same logic as _paginate)
            trip_rate = None
            trip_remaining = None
            if history.trip and history.trip.assigned_vendor:
                # Calculate balance_amount (total trip cost)
                # Formula: trip_rate + other_unloading_charges + other_charges - deducted_amount - pod_penalty_amount
                balance_amount = (
                    (history.trip.assigned_vendor.trip_rate or Decimal("0.0")) + 
                    (history.trip.assigned_vendor.other_unloading_charges or Decimal("0.0")) + 
                    (history.trip.assigned_vendor.other_charges or Decimal("0.0")) - 
                    (history.trip.deducted_amount or Decimal("0.0")) - 
                    (history.trip.pod_penalty_amount or Decimal("0.0"))
                )
                trip_rate = balance_amount
                
                # Get payments for this trip from pre-fetched data
                previous_payments = payments_by_trip.get(history.trip.id, [])
                paid_amount = sum(payment.amount for payment in previous_payments if payment.amount and payment.is_paid_amount is True)
                
                # Calculate remaining amount
                trip_remaining = balance_amount - paid_amount
            
            converted_results.append(PaymentApprovalHistoryRead(
                id=history.id,
                trip_id=history.trip_id,
                approval_type=history.approval_type,
                approved_by=history.approved_by,
                approver_name=history.approver.name if history.approver else None,
                trip_code=history.trip.trip_code if history.trip else None,
                trip_rate=trip_rate,
                trip_remaining=trip_remaining,
                customer=customer,
                vendor=vendor,
                remarks=history.remarks,
                created_at=history.created_at,
            ))
        
        return PaymentApprovalHistoryList(
            total=total,
            next=next_url,
            previous=previous_url,
            results=converted_results
        )