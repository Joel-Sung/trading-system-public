from datetime import datetime
from zoneinfo import ZoneInfo


def get_dt_from_ms(ms: float) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=ZoneInfo("Asia/Singapore"))


def get_current_dt() -> datetime:
    return datetime.now(ZoneInfo("Asia/Singapore"))


def format_dt(dt: datetime | None = None) -> str:
    if dt is None:
        dt = get_current_dt()

    return dt.strftime("%Y-%m-%dT%H-%M-%S")


def format_date(date: datetime | None = None) -> str:
    if date is None:
        date = get_current_dt()

    return date.strftime("%Y-%m-%d")
