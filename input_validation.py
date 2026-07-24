import re
from typing import Optional, Tuple


def parse_int(value: str) -> Optional[int]:
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_float(value: str) -> Optional[float]:
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_time_signature(value: str) -> Optional[Tuple[int, int]]:
    text = value.strip()
    match = re.fullmatch(r"(\d{1,2})\s*/\s*(\d{1,2})", text)
    if not match:
        return None
    numerator = int(match.group(1))
    denominator = int(match.group(2))
    if numerator <= 0 or denominator <= 0:
        return None
    return numerator, denominator


def run_common_validation_checks() -> None:
    assert parse_int("12") == 12
    assert parse_int("abc") is None
    assert parse_float("1.5") == 1.5
    assert parse_float("") is None
    assert parse_time_signature("4/4") == (4, 4)
    assert parse_time_signature("7 / 8") == (7, 8)
    assert parse_time_signature("0/4") is None
