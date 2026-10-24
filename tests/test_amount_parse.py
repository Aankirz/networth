"""The monthly amount, typed the way people type it."""

from __future__ import annotations

import pytest

from networth.bot.onboarding import Money, format_money, parse_amount


@pytest.mark.parametrize(
    ("text", "amount", "currency"),
    [
        ("1 lakh", 100_000, "INR"),
        ("1.5L", 150_000, "INR"),
        ("₹50,000", 50_000, "INR"),
        ("50k", 50_000, "INR"),
        ("25k", 25_000, "INR"),
        ("$500", 500, "USD"),
        ("500 dollars", 500, "USD"),
        ("10,00,000", 1_000_000, "INR"),
        ("1 crore", 10_000_000, "INR"),
        ("rs 5000", 5_000, "INR"),
        ("INR 2,500", 2_500, "INR"),
        ("usd 1200", 1_200, "USD"),
        ("$1000", 1_000, "USD"),
        ("about 2 lakhs a month", 200_000, "INR"),
    ],
)
def test_parses(text: str, amount: int, currency: str) -> None:
    assert parse_amount(text) == Money(amount, currency)


@pytest.mark.parametrize("text", ["", "abc", "0", "-5", "lots", "₹0", "5 years", "$5"])
def test_rejects(text: str) -> None:
    assert parse_amount(text) is None


@pytest.mark.parametrize(
    ("amount", "currency", "shown"),
    [(1_000, "INR", "₹1,000"), (100_000, "INR", "₹1,00,000"), (1_000_000, "INR", "₹10,00,000"),
     (999, "INR", "₹999"), (12_345_678, "INR", "₹1,23,45,678"), (1_000, "USD", "$1,000")],
)  # fmt: skip
def test_formats_money_the_local_way(amount: int, currency: str, shown: str) -> None:
    assert format_money(amount, currency) == shown
