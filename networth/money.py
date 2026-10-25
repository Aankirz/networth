"""The one money formatter: an amount in the user's own currency, words in their language.

    money(291000, "INR")            # "₹2.91 lakh"
    money(12000000, "INR", "hi")    # "₹1.2 करोड़"
    money(45000, "INR")             # "₹45,000"
    money(12400, "USD")             # "$12,400"
    money(1_200_000, "USD")         # "$1.2M"
    money(-4000, "INR", signed=True)  # "−₹4,000"; +₹6,000 for a gain

Rupees group in lakhs and crores, dollars in thousands and millions. Any other currency gets its
code and western grouping ("EUR 1,250"); no currency at all is rupees, the app's default.
Compact amounts keep two decimals at most and drop trailing zeros, never rounding to a whole.
"""

from __future__ import annotations

from typing import Final

MINUS: Final = "−"
SYMBOLS: Final = {"INR": "₹", "USD": "$"}
LAKH, CRORE = 10**5, 10**7
THOUSAND_CAP, MILLION, BILLION = 10**5, 10**6, 10**9  # $99,999 stays whole; $100K is short
INDIAN_UNITS: Final = {
    "en": ("lakh", "crore"),
    "hinglish": ("lakh", "crore"),
    "hi": ("लाख", "करोड़"),
}


def indian_grouping(n: int) -> str:
    """1,23,45,678: the last three digits, then pairs."""
    digits = str(n)
    head, tail = digits[:-3], digits[-3:]
    pairs = [head[max(0, i - 2) : i] for i in range(len(head), 0, -2)]
    return ",".join([*reversed(pairs), tail]) if head else tail


def short(n: float, unit: int) -> str:
    """n in units of `unit`, two decimals at most, trailing zeros dropped: 2.91, 1.2, 3."""
    return f"{n / unit:.2f}".rstrip("0").rstrip(".")


def rupees(n: float, lang: str | None) -> str:
    lakh, crore = INDIAN_UNITS.get(lang or "en", INDIAN_UNITS["en"])
    if n >= CRORE:
        return f"₹{short(n, CRORE)} {crore}"
    if n >= LAKH:
        return f"₹{short(n, LAKH)} {lakh}"
    return f"₹{indian_grouping(round(n))}"


def dollars(n: float) -> str:
    if n >= BILLION:
        return f"${short(n, BILLION)}B"
    if n >= MILLION:
        return f"${short(n, MILLION)}M"
    if n >= THOUSAND_CAP:
        return f"${short(n, 1000)}K"
    return f"${round(n):,}"


def money(amount: float, currency: str | None = "INR", lang: str | None = "en", *,
          signed: bool = False) -> str:  # fmt: skip
    """The amount in its currency; signed puts + on a gain. A loss always gets a minus sign."""
    code = (currency or "INR").upper()
    n = abs(amount)
    if code == "INR":
        body = rupees(n, lang)
    elif code == "USD":
        body = dollars(n)
    else:
        body = f"{code} {round(n):,}"
    if round(amount) < 0:
        return f"{MINUS}{body}"
    return f"+{body}" if signed and round(amount) > 0 else body
