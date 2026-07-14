from datetime import datetime, date
from django.utils import timezone

def normalize_date(value):
    """
    Converts a date or naive datetime object to an aware datetime.
    """
    if isinstance(value, datetime):
        return timezone.make_aware(value) if timezone.is_naive(value) else value
    if isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time())
        return timezone.make_aware(dt)
    return None

def parse_date_range(from_str, to_str):
    """
    Parses start and end date strings (YYYY-MM-DD) into aware datetime objects
    representing the absolute start of from_str and end of to_str.
    """
    from_dt = timezone.make_aware(
        datetime.strptime(from_str, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    )
    to_dt = timezone.make_aware(
        datetime.strptime(to_str, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
    )
    return from_dt, to_dt
