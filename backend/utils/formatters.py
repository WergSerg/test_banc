from decimal import Decimal
from typing import Optional


def format_currency(amount: Decimal, currency: str = "RUB") -> str:
    return f"{amount:.2f} {currency}"


def parse_currency(amount_str: str) -> Decimal:
    amount_str = amount_str.replace("RUB", "").strip()
    return Decimal(amount_str)


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix
