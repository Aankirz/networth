"""The holdings words eval's fixed inputs, offline: the set's size and languages, and the eval
user's recorded portfolio producing a report."""

from __future__ import annotations

from pathlib import Path

from evals import words
from evals.holdings_words import MESSAGES, eval_store
from networth import holdings
from tests.test_sim_web import TABLE


def test_the_set_has_at_least_25_messages_in_all_three_languages() -> None:
    assert len(MESSAGES) >= 25
    assert {lang for *_, lang in MESSAGES} == {"en", "hi", "hinglish"}


def test_the_eval_user_holds_the_recorded_portfolio_and_gets_a_report(tmp_path: Path) -> None:
    store = eval_store(tmp_path)
    text = holdings.holdings_message(words.USER.user_id, store, table=TABLE)
    assert text is not None and "Parag Parikh Flexi Cap Fund Direct Growth" in text
