"""Phase 12: the holdings reply leads with the answer. The owner's real Groww screenshot
(groww_owner.png, four single company shares) is read through its recorded vision answer, so
the numbers here are the screenshot's own: units, average cost, invested, price and value."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from networth import guard
from networth import holdings as nh
from networth.bot import holdings_words as words
from networth.bot.message import FOOTER, plain
from networth.holdings.lines import history_lines
from networth.holdings.model import Bucket, Kind, bucket_for, from_json
from networth.holdings.summary import summarize
from networth.llm import WireHoldings
from tests.test_bot_holdings import (  # noqa: F401  fixed_table is an autouse fixture
    LANGS,
    FakeModels,
    buttons,
    fixed_table,
    last,
    photo,
    talk,
)
from tests.test_holdings import FIXTURES
from tests.test_onboarding import USER, Chat
from tests.test_sim_web import TABLE

OWNER = json.loads((FIXTURES / "groww_owner_vision.json").read_text())
INTERNAL = re.compile(r"\b(growth|core|safety)\b|सेफ़्टी|कोर|ग्रोथ|\d+ (units|cost) \d", re.I)


def wire(rows: slice = slice(None), **changes: object) -> WireHoldings:
    return WireHoldings.model_validate({**OWNER, "rows": OWNER["rows"][rows], **changes})


class Screens(FakeModels):
    """Each read is the next screenshot's recorded answer."""

    def __init__(self, *screens: WireHoldings) -> None:
        super().__init__()
        self.screens = list(screens)

    def read_holdings(self, image: bytes, mime: str, lang: str) -> WireHoldings | None:
        return self.screens.pop(0)


def owner(tmp_path: Path, *screens: WireHoldings, lang: str = "en") -> Chat:
    return talk(tmp_path, Screens(*screens or (wire(),)), lang=lang)


def stored(chat: Chat):
    return from_json(chat.store.holdings_data(USER))


def test_the_owners_screenshot_gives_the_worth_the_loss_and_each_share(tmp_path) -> None:
    chat = owner(tmp_path)
    photo(chat)
    m = last(chat)
    assert m.title == "Got it. 4 holdings, worth ₹2.91 lakh today."
    assert m.body[0] == "You put in ₹3.25 lakh, so you're down ₹34,373 (11%)."
    assert m.body[1].splitlines() == [
        "Adani Green Energy: ₹2.13 lakh, 73% of this",
        "Swiggy: ₹68,640, 24%",
        "Vishal Nirmiti: ₹7,881, 3%",
        "Hero Motors: ₹775, under 1%",
    ]
    assert (
        m.body[2]
        == "All 4 are single company shares. Adani Green Energy alone is 73% of this money."
    )
    assert m.body[-1] == words.EVERYTHING["en"] and m.footer == ""
    assert [d for _, d, _ in buttons(chat)] == ["hd:ok", "hd:more", "hd:fix"]


def test_the_totals_are_the_screenshots_own_printed_numbers(tmp_path) -> None:
    chat = owner(tmp_path)
    photo(chat)
    s = summarize(stored(chat))
    printed_value = sum(r["current_value"] for r in OWNER["rows"])  # 2,90,614.52
    printed_cost = sum(r["invested"] for r in OWNER["rows"])  # 3,24,987.20
    printed_returns = -21_079.50 - 7_078.80 - 5_904.00 - 310.38
    assert (s.value, s.invested) == (round(printed_value), round(printed_cost))
    assert s.gain == round(printed_returns) == -34_373


@pytest.mark.parametrize("lang", LANGS)
def test_every_language_leads_with_the_worth(tmp_path, lang: str) -> None:
    chat = owner(tmp_path, lang=lang)
    photo(chat)
    lakh = "लाख" if lang == "hi" else "lakh"
    assert f"₹2.91 {lakh}" in last(chat).title and "₹68,640" in plain(last(chat))


def test_a_cut_off_list_says_how_many_it_can_see(tmp_path) -> None:
    chat = owner(tmp_path, wire(listed=22), wire(more_below=True))
    photo(chat)
    assert last(chat).body[-1] == "I can see 4 of your 22. Scroll in your app and send the rest."
    chat.tap("hd:cancel")
    photo(chat)
    assert last(chat).body[-1].startswith("I can see 4 here, and the list goes on.")


def test_a_second_screenshot_adds_rows_without_duplicates(tmp_path) -> None:
    chat = owner(tmp_path, wire(slice(0, 3)), wire(slice(2, 4)))
    photo(chat)
    assert last(chat).title == "Got it. 3 holdings, worth ₹2.9 lakh today."
    chat.tap("hd:more")
    assert chat.bot.last == words.SEND_NEXT["en"].format(count=3)
    photo(chat)
    names = [x.name for x in stored(chat).items]
    assert names == ["Swiggy", "Vishal Nirmiti", "Adani Green Energy", "Hero Motors"]
    assert last(chat).title == "Got it. 4 holdings, worth ₹2.91 lakh today."
    assert last(chat).body[0] == "This screenshot added 1. Already on the list, so updated: 1."


def test_thats_everything_compares_with_the_plan_in_rupees(tmp_path) -> None:
    chat = owner(tmp_path)
    photo(chat)
    chat.tap("hd:ok")
    m = last(chat)
    assert stored(chat).confirmed and m.title == "Saved." and m.footer == FOOTER["en"]
    assert m.body == (
        "Your plan is Balanced: about 20% in safe money (liquid, gilt, FD), 70% in broad index "
        "funds and 10% in single shares or themes.",
        "Right now 100% is in single shares or themes.",
        "The part furthest from your plan is single shares or themes: at your plan's 10% that "
        "would be about ₹29,061, and right now it is ₹2.91 lakh. That's the part worth reading "
        "about first.",
    )
    assert [(label, d) for label, d, _ in buttons(chat)] == [
        ("Show my plan", "br:plan"), ("What would history say?", "hd:history")]  # fmt: skip


def test_what_would_history_say_gives_the_history_lines(tmp_path) -> None:
    chat = owner(tmp_path)
    photo(chat)
    chat.tap("hd:ok")
    chat.tap("hd:history")
    report = nh.report_for(USER, chat.store, table=TABLE)
    first, *rest = history_lines(report.history, "en")
    assert last(chat).title == first and last(chat).body == tuple(rest)
    assert last(chat).footer == FOOTER["en"]


def test_somethings_wrong_fixes_a_holding_through_buttons_and_plain_words(tmp_path) -> None:
    chat = owner(tmp_path)
    photo(chat)
    chat.tap("hd:fix")
    assert chat.bot.last == "Which one is off?"
    assert [(label, d) for label, d, _ in buttons(chat)] == [
        ("Swiggy", "hd:pick:1"), ("Vishal Nirmiti", "hd:pick:2"),
        ("Adani Green Energy", "hd:pick:3"), ("Hero Motors", "hd:pick:4"),
        ("Start over", "hd:cancel")]  # fmt: skip
    chat.tap("hd:pick:1")
    assert chat.bot.last.startswith("What's the right number for Swiggy?")
    assert [d for _, d, _ in buttons(chat)][-1] == "hd:drop:1"
    chat.say("hmm")
    assert chat.bot.last == words.NOT_CAUGHT["en"] and stored(chat).items[0].units == 390
    chat.say("15 shares")
    assert stored(chat).items[0].units == 15 and stored(chat).fixing == 0
    assert last(chat).body[0] == "Updated Swiggy."
    chat.tap("hd:fix")
    chat.tap("hd:pick:4")
    chat.say("remove it")
    assert [x.name for x in stored(chat).items] == [
        "Swiggy",
        "Vishal Nirmiti",
        "Adani Green Energy",
    ]
    assert last(chat).body[0] == "Removed Hero Motors."
    chat.tap("hd:fix")
    chat.tap("hd:pick:2")
    chat.tap("hd:kind:2:core")
    assert stored(chat).items[1].bucket is Bucket.CORE and not stored(chat).confirmed


def test_the_remove_button_drops_the_line(tmp_path) -> None:
    chat = owner(tmp_path)
    photo(chat)
    chat.tap("hd:pick:2")
    chat.tap("hd:drop:2")
    assert len(stored(chat).items) == 3 and last(chat).body[0] == "Removed Vishal Nirmiti."


def _every_reply(tmp_path: Path, lang: str) -> list[str]:
    chat = owner(tmp_path, wire(slice(0, 2), listed=4), wire(slice(1, 4), more_below=True),
                 lang=lang)  # fmt: skip
    start, sent = len(chat.bot.messages), len(chat.bot.sent)
    for step in ("photo", "hd:more", "photo", "hd:fix", "hd:pick:1", "say:huh", "say:15 shares",
                 "hd:pick:2", "hd:kind:2:growth", "hd:ok", "hd:history", "say:/holdings",
                 "say:what should I sell?", "say:kya bechna chahiye"):  # fmt: skip
        if step == "photo":
            photo(chat)
        elif step.startswith("say:"):
            chat.say(step[4:])
        else:
            chat.tap(step)
    texts = [plain(m) for m in chat.bot.messages[start:]]
    labels = [b.label for _, _, rows in chat.bot.sent[sent:] for row in rows for b in row]
    return texts + labels


@pytest.mark.parametrize("lang", LANGS)
def test_no_holdings_reply_has_an_internal_word_or_the_old_syntax(tmp_path, lang: str) -> None:
    replies = _every_reply(tmp_path, lang)
    assert len(replies) > 20
    for text in replies:
        assert not INTERNAL.search(text), text
        assert guard.check(text, text).ok, (text, guard.check(text, text).problems)


def test_what_should_i_sell_gets_the_gap_and_history_never_a_pick(tmp_path) -> None:
    chat = owner(tmp_path)
    photo(chat)
    chat.tap("hd:ok")
    chat.say("Which of these should I sell?")
    text = plain(last(chat))
    assert text.startswith(words.NOT_A_PICK["en"])
    assert "The part furthest from your plan is single shares or themes" in text
    assert "₹29,061" in text and guard.check(text, text).ok
    for name in ("Swiggy", "Vishal Nirmiti", "Adani Green Energy", "Hero Motors"):
        assert name not in text


@pytest.mark.parametrize("name, kind, ticker", [
    ("GOLDBEES", Kind.ETF, None), ("Nippon India ETF Gold BeES", Kind.ETF, "GOLDBEES"),
    ("SILVERBEES", Kind.ETF, None), ("HDFC Gold Fund Direct Growth", Kind.MUTUAL_FUND, None),
    ("ICICI Prudential Silver ETF", Kind.ETF, "SILVERIETF")])  # fmt: skip
def test_gold_and_silver_are_safe_money(name: str, kind: Kind, ticker: str | None) -> None:
    assert bucket_for(name, kind, ticker) is Bucket.SAFETY


def test_goldbees_shows_as_safe_money_in_the_plan_comparison(tmp_path) -> None:
    gold = {
        **OWNER["rows"][0],
        "name": "GOLDBEES",
        "kind": "etf",
        "units": 100.0,
        "avg_cost": 60.0,
        "invested": 6000.0,
        "current_price": 70.0,
        "current_value": 7000.0,
    }
    chat = owner(tmp_path, WireHoldings.model_validate({**OWNER, "rows": [*OWNER["rows"], gold]}))
    photo(chat)
    assert stored(chat).items[-1].bucket is Bucket.SAFETY
    chat.tap("hd:ok")
    assert "2% is in safe money (liquid, gilt, FD)" in plain(last(chat))
