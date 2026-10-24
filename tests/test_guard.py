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
