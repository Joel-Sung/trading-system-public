from datetime import datetime
from zoneinfo import ZoneInfo


def get_datetime_from_milliseconds(ms) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=ZoneInfo("Asia/Singapore"))


def get_current_datetime() -> datetime:
    return datetime.now(ZoneInfo("Asia/Singapore"))


def format_datetime(dt: datetime | None = None) -> str:
    if dt is None:
        dt = get_current_datetime()

    return dt.strftime("%Y-%m-%dT%H-%M-%S")


def format_date(date: datetime | None = None) -> str:
    if date is None:
        date = get_current_datetime()

    return date.strftime("%Y-%m-%d")
