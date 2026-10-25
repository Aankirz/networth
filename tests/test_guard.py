"""The send gate: invented numbers, banned words and advice phrasing never reach a user."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from networth import guard

SOURCE = (
    "Investing day, Nov 1. ₹1,00,000 ready. Indian banks beat the Nifty 50 in 14 of 22 "
    "past RBI rate hikes. In a normal month, 56%. Weak signal. Your plan: 20% safety, "
    "70% core, 10% growth."
)
TEMPLATE = "Indian banks beat the Nifty 50 in 14 of 22 past RBI rate hikes. In a normal month, 56%."
GOOD = "On Nov 1, with ₹1 lakh ready: banks beat the Nifty 50 in 14 of 22 past hikes (normal 56%)."
INVENTED = "Banks beat the Nifty 50 in 15 of 22 past hikes."


class Writer:
    """Hands back drafts in order and remembers the feedback it was given."""

    def __init__(self, *drafts: str) -> None:
        self.drafts = list(drafts)
        self.feedback: list[str | None] = []

    def __call__(self, feedback: str | None) -> str:
        self.feedback.append(feedback)
        return self.drafts.pop(0)


def test_a_draft_using_only_source_numbers_in_any_format_passes() -> None:
    assert guard.check(GOOD, SOURCE).ok
    assert guard.check("बैंक 22 में से १४ बार आगे रहे।", SOURCE).ok


def test_an_invented_number_is_named() -> None:
    assert guard.check(INVENTED, SOURCE).problems == ("number 15 is not in the source",)


@pytest.mark.parametrize(
    "text",
    [
        "Banks look like a buy this month.",
        "Time to sell IT.",
        "This is a sure shot multibagger.",
        "Returns are guaranteed.",
        "Banks ka target price badh gaya.",
        "Abhi bank shares kharido.",
        "IT wale becho yaar.",
        "Pakka munafa hoga.",
    ],
)
def test_banned_words_are_blocked_in_english_and_hinglish(text: str) -> None:
    assert any(p.startswith("banned word") for p in guard.check(text, SOURCE).problems)


@pytest.mark.parametrize(
    "text",
    [
        "You should put more into banks.",
        "Put your money in index funds.",
        "Move ₹20,000 into debt.",
        "Apply for this IPO before Friday.",
        "Skip this one.",
        "Aapko banks mein invest karna chahiye.",
        "Thoda paisa banks mein lagao.",
        "Is IPO ko skip karo.",
    ],
)
def test_advice_phrasing_is_blocked_in_english_and_hinglish(text: str) -> None:
    assert any(p.startswith("advice phrasing") for p in guard.check(text, SOURCE).problems)


def test_a_passing_draft_is_sent_as_written(tmp_path: Path) -> None:
    out = guard.guarded(Writer(GOOD), SOURCE, TEMPLATE, tmp_path / "g.jsonl", "brief")
    assert (out.text, out.used) == (GOOD, "model")


def test_an_invented_number_is_rewritten_once_with_the_problem_named(tmp_path: Path) -> None:
    writer = Writer(INVENTED, GOOD)
    out = guard.guarded(writer, SOURCE, TEMPLATE, tmp_path / "g.jsonl", "brief")
    assert (out.text, out.used) == (GOOD, "rewrite")
    assert writer.feedback == [None, "number 15 is not in the source"]


def test_a_second_failure_sends_the_template_and_logs_every_verdict(tmp_path: Path) -> None:
    log = tmp_path / "g.jsonl"
    out = guard.guarded(Writer(INVENTED, "You should buy banks."), SOURCE, TEMPLATE, log, "brief")
    assert (out.text, out.used) == (TEMPLATE, "template")
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert [(r["attempt"], r["ok"]) for r in rows] == [
        ("model", False),
        ("rewrite", False),
        ("template", True),
    ]


def test_a_writer_that_raises_falls_back_to_the_template(tmp_path: Path) -> None:
    def broken(feedback: str | None) -> str:
        raise TimeoutError("no answer")

    out = guard.guarded(broken, SOURCE, TEMPLATE, tmp_path / "g.jsonl", "brief")
    assert (out.text, out.used) == (TEMPLATE, "template")


@pytest.mark.parametrize("text", ["Rs5000 gain typical", "Rs.5000 gain typical",
                                  "INR5000 gain typical", "５０００ gain typical"])  # fmt: skip
def test_a_number_glued_to_a_currency_or_fullwidth_is_still_checked(text: str) -> None:
    assert "number 5000 is not in the source" in guard.check(text, SOURCE).problems


@pytest.mark.parametrize("text", ["Banks rose fifty percent of the time",
                                  "Banks beat the Nifty half the time",
                                  "Prices doubled twice", "seventy-five past hikes"])  # fmt: skip
def test_number_words_must_be_in_the_source(text: str) -> None:
    source = "Banks beat the market in 14 of 22 past hikes (normal 56%)."
    assert any(p.startswith("number word") for p in guard.check(text, source).problems)


def test_number_words_the_source_backs_pass() -> None:
    source = "Retail quota: 50%. Depends on three suppliers. Twenty-two past hikes."
    assert guard.check("Half the shares, three suppliers, twenty-two hikes.", source).ok


@pytest.mark.parametrize("text", [
    "Investors should hold banks",
    "I recommend banks",
    "आपको निवेश करना चाहिए",
    "Abhi daal dein",
    "s e l l now",
    "b​uy now",
    "Lambe time tak ruko, ghabrao mat",
    "Thoda ruk jaiye aur dekhiye",
    "Paisa nikaal lo",
    "Yeh fund sabse acha score karta hai",
    "Banks rank first",
    "Abhi invest kijiye",
    "कृपया निवेश करें",
])  # fmt: skip
def test_advice_and_ranking_in_any_spelling_is_blocked(text: str) -> None:
    assert not guard.check(text, text).ok


# Live replies from 2026-10-25 (docs/phases/phase-3b-report.md) with the text they came from.
LIVE = json.loads((Path(__file__).parent / "fixtures" / "guard_live.json").read_text("utf-8"))


@pytest.mark.parametrize("case", LIVE)
def test_normal_brief_why_explain_and_hinglish_replies_still_pass(case: dict) -> None:
    assert guard.check(case["reply"], case["source"]).problems == ()


@pytest.mark.parametrize(("text", "want"), [
    ("Yeh simple hota—but asli", "Yeh simple hota, but asli"),
    ("IPO hai — company ka", "IPO hai, company ka"),
    ("Price band ₹410–432", "Price band ₹410–432"),
])  # fmt: skip
def test_long_dashes_from_the_writer_become_commas_but_ranges_stay(text: str, want: str) -> None:
    from networth.llm import undash

    assert undash(text) == want


def test_every_glossary_row_passes_the_guard() -> None:
    glossary = Path(__file__).parents[1] / "knowledge" / "glossary.md"
    rows = [line for line in glossary.read_text().splitlines() if line.startswith("| ")]
    cells = [c.strip() for row in rows for c in row.strip("|").split("|")[1:]]
    failing = {c: guard.check(c, c).problems for c in cells if not guard.check(c, c).ok}
    assert failing == {}, "the writer copies glossary wording, so it must read as description"
