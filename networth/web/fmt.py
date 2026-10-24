"""Number formatting for the pages. Formats engine numbers; never computes new ones."""

from __future__ import annotations

from typing import Final

MINUS: Final = "−"
SYMBOLS: Final[dict[str, str]] = {"INR": "₹", "USD": "$"}


def indian_grouping(n: int) -> str:
    """1,23,45,678: the last three digits, then pairs."""
    digits = str(abs(n))
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while head:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    grouped = ",".join([*pairs, tail]) if pairs else tail
    return f"{MINUS}{grouped}" if n < 0 else grouped


def western_grouping(n: int) -> str:
    grouped = f"{abs(n):,}"
    return f"{MINUS}{grouped}" if n < 0 else grouped


def money(n: int, currency: str, *, signed: bool = True) -> str:
    """−₹4,000 / +₹6,000 in Indian grouping, −$258 / +$211 in western grouping."""
    grouping = indian_grouping if currency == "INR" else western_grouping
    body = f"{SYMBOLS[currency]}{grouping(abs(n))}"
    if n < 0:
        return f"{MINUS}{body}"
    return f"+{body}" if signed and n > 0 else body


def percent(rate: float) -> str:
    return f"{round(rate * 100)}%"


def signed_percent(ret: float) -> str:
    """A return as +3.2% / −1.4%, one decimal."""
    text = f"{abs(ret) * 100:.1f}%"
    if text == "0.0%":
        return text
    return f"{MINUS}{text}" if ret < 0 else f"+{text}"
