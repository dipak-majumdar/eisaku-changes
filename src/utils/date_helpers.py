from datetime import datetime, date, timedelta
from typing import Tuple, Optional
from models.enums import TimePeriodEnum


def get_date_range(
    time_period: Optional[TimePeriodEnum] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Get date range based on time period or custom dates.
    Returns (start_datetime, end_datetime)
    """
    now = datetime.now()
    today = now.date()
    
    if time_period == TimePeriodEnum.TODAY:
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        return (start, end)
    
    elif time_period == TimePeriodEnum.THIS_WEEK:
        # Week starts on Monday
        start_of_week = today - timedelta(days=today.weekday())
        start = datetime.combine(start_of_week, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        return (start, end)
    
    elif time_period == TimePeriodEnum.THIS_MONTH:
        start = datetime(now.year, now.month, 1, 0, 0, 0)
        end = datetime.combine(today, datetime.max.time())
        return (start, end)
    
    elif time_period == TimePeriodEnum.THIS_QUARTER:
        quarter = (now.month - 1) // 3
        quarter_start_month = quarter * 3 + 1
        start = datetime(now.year, quarter_start_month, 1, 0, 0, 0)
        end = datetime.combine(today, datetime.max.time())
        return (start, end)
    
    elif time_period == TimePeriodEnum.THIS_YEAR:
        start = datetime(now.year, 1, 1, 0, 0, 0)
        end = datetime.combine(today, datetime.max.time())
        return (start, end)
    
    elif time_period == TimePeriodEnum.LAST_YEAR:
        start = datetime(now.year - 1, 1, 1, 0, 0, 0)
        end = datetime(now.year - 1, 12, 31, 23, 59, 59)
        return (start, end)
    
    elif time_period == TimePeriodEnum.CUSTOM:
        # Use provided start_date and end_date
        if start_date and end_date:
            start = datetime.combine(start_date, datetime.min.time())
            end = datetime.combine(end_date, datetime.max.time())
            return (start, end)
        elif start_date:
            start = datetime.combine(start_date, datetime.min.time())
            return (start, None)
        elif end_date:
            end = datetime.combine(end_date, datetime.max.time())
            return (None, end)
    
    # No filtering
    return (None, None)
