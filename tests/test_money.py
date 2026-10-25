"""networth.money: rupees in lakhs and crores, dollars in K and M, in the user's language."""

from __future__ import annotations

import pytest

from networth.money import money

INR = [
    (0, "₹0"),
    (999, "₹999"),
    (45000, "₹45,000"),
    (99999, "₹99,999"),
    (100000, "₹1 lakh"),
    (291000, "₹2.91 lakh"),
    (291234, "₹2.91 lakh"),
    (9950000, "₹99.5 lakh"),
    (12000000, "₹1.2 crore"),
    (123456789, "₹12.35 crore"),
]
USD = [
    (0, "$0"),
    (12400, "$12,400"),
    (99999, "$99,999"),
    (450000, "$450K"),
    (1_200_000, "$1.2M"),
    (2_500_000_000, "$2.5B"),
]


@pytest.mark.parametrize(("amount", "text"), INR)
def test_rupees_use_lakh_and_crore(amount: int, text: str) -> None:
    assert money(amount, "INR") == text


@pytest.mark.parametrize(("amount", "text"), USD)
def test_dollars_use_k_and_m_never_lakh(amount: int, text: str) -> None:
    assert money(amount, "USD") == text
    assert "lakh" not in text and "₹" not in text


def test_hindi_words_the_units_and_hinglish_keeps_lakh() -> None:
    assert money(291000, "INR", "hi") == "₹2.91 लाख"
    assert money(12000000, "INR", "hi") == "₹1.2 करोड़"
    assert money(291000, "INR", "hinglish") == "₹2.91 lakh"


def test_signs_minus_on_a_loss_and_plus_only_when_asked() -> None:
    assert money(-4000, "INR") == "−₹4,000"
    assert money(-1_200_000, "USD") == "−$1.2M"
    assert money(6000, "INR", signed=True) == "+₹6,000"
    assert money(0, "USD", signed=True) == "$0"


def test_an_unknown_currency_gets_its_code_and_none_means_rupees() -> None:
    assert money(1250, "EUR") == "EUR 1,250"
    assert money(291000, None) == "₹2.91 lakh"
    assert money(12400, "usd") == "$12,400"
