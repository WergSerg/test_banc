from datetime import date, datetime
from typing import Optional, Union

import pytz


def now() -> datetime:
    return datetime.utcnow()


def to_iso_format(dt: Optional[datetime]) -> Optional[str]:
    if dt:
        return dt.isoformat()
    return None


def from_iso_format(iso_str: Optional[str]) -> Optional[datetime]:
    if iso_str:
        return datetime.fromisoformat(iso_str)
    return None


def format_date(dt: Union[datetime, date], format: str = "%Y-%m-%d") -> str:
    return dt.strftime(format)


def parse_date(date_str: str, format: str = "%Y-%m-%d") -> date:
    return datetime.strptime(date_str, format).date()
