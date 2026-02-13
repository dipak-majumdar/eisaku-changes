import os
import sys
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal

# Add project root (where src/ is) to PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(BASE_DIR.__str__())

from sqlmodel import Session, select

from db.session import engine
from models.trip import Trip, TripStatusEnum
from models.advance_payment import AdvancePayment


def apply_pod_late_fees():
    """
    Checks for trips with status 'VEHICLE_UNLOADED' where the POD submission
    is overdue (more than 18 days after unloading) and creates a daily
    late fee record in AdvancePayment.
    """
    print("🚀 Starting POD late fee calculation...")
    
    with Session(engine) as session:
        # Find trips that are in the "Vehicle Unloaded" state.
        # The properties on the Trip model will handle the date logic.
        overdue_trips = session.exec(
            select(Trip).where(Trip.status == TripStatusEnum.VEHICLE_UNLOADED)
        ).all()

        print(f"Found {len(overdue_trips)} trips with status 'VEHICLE_UNLOADED'.")
        
        today = date.today()
        late_fee_type = "POD Late Fine"
        fee_amount = Decimal("100.00")
        created_count = 0

        for trip in overdue_trips:
            # The pod_overdue_days property calculates days past the due date.
            if trip.pod_overdue_days > 0 and trip.pod_submission_last_date:
                
                # Loop from the first overdue day until today.
                start_penalty_date = trip.pod_submission_last_date + timedelta(days=1)
                
                for i in range(trip.pod_overdue_days):
                    penalty_date = start_penalty_date + timedelta(days=i)

                    # Ensure we don't create future penalties
                    if penalty_date > today:
                        continue

                    # Check if a penalty for this trip on this date already exists.
                    existing_fee = session.exec(
                        select(AdvancePayment).where(
                            AdvancePayment.trip_id == trip.id,
                            AdvancePayment.payment_date == penalty_date,
                            AdvancePayment.payment_type == late_fee_type
                        )
                    ).first()

                    if not existing_fee and trip.assigned_vendor:
                        # Create a new late fee record.
                        new_fee = AdvancePayment(
                            trip_id=trip.id,
                            vendor_id=trip.assigned_vendor.vendor_id,
                            amount=fee_amount,
                            payment_date=penalty_date,
                            payment_type=late_fee_type,
                            is_paid_amount=False, # It's a payable, not a payment yet.
                        )
                        session.add(new_fee)
                        created_count += 1
        
        session.commit()
        print(f"✅ Successfully created {created_count} new POD late fee records.")

if __name__ == "__main__":
    apply_pod_late_fees()
