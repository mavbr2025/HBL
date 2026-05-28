from decimal import Decimal, InvalidOperation
from typing import Any


def normalize_for_compare(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.strip().casefold().split())


def is_blank(value: object | None) -> bool:
    if value is None:
        return True
    return str(value).strip() == ""


def decimal_from_display(value: str) -> Decimal | None:
    cleaned = value.replace(",", "").strip()
    parts = cleaned.split()
    if parts:
        cleaned = parts[0]
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def get_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
            if callable(current):
                current = current()
    return current
