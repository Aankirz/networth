"""Holdings on Telegram end to end: a screenshot becomes a list to check, Looks right gives the
report, a fix or a cancel changes the stored list, /holdings and a holdings question in chat.
No network: the vision answer is the recorded one for groww_fake.png and prices are a fake."""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Sequence
from pathlib import Path

import pytest

from networth import holdings as nh
from networth.app.services import Services
from networth.bot import holdings as flow
from networth.bot.message import FOOTER, Message, plain
from networth.chat import explain
from networth.holdings.model import from_json
from networth.llm import WireHoldings
from networth.net import CallFailed
from tests.test_holdings import PNG, Recorded
from tests.test_links import SECRET
from tests.test_onboarding import CHAT, NOW, USER, Chat, onboard
from tests.test_sim_web import TABLE

LANGS = ("en", "hi", "hinglish")
NAMES = ("UTI Nifty 50 Index Fund", "HDFC Liquid Fund", "Parag Parikh", "Reliance",
         "Tata Motors", "Bank BeES", "Infosys")  # fmt: skip
_ids = itertools.count(10_000)


class FakeModels:
    """The vision read is the recorded Groww answer, or None for a picture of something else."""

    def __init__(self, *, holdings: bool = True, intent: str | None = None,
                 writes: Sequence[str] = ()) -> None:  # fmt: skip
        self.holdings, self.intent, self.writes = holdings, intent, list(writes)
        self.images: list[bytes] = []

    def read_holdings(self, image: bytes, mime: str, lang: str) -> WireHoldings | None:
        return Recorded().read_holdings(image, mime, lang) if self.holdings else None

    def read_image(self, image: bytes, mime: str) -> str:
        self.images.append(image)
        raise CallFailed("read_image", "scripted")

    def pick(self, question: str, choices: object, text: str) -> str | None:
        return self.intent

    def write(self, task: str, facts: str, feedback: str | None = None) -> str:
        if not self.writes:
            raise CallFailed("write", "no scripted draft")
        return self.writes.pop(0)


class NoPrices:
    def quote(self, symbol: str) -> tuple[float, str] | None:
        return None


def services(tmp_path: Path, models: FakeModels | None = None, **kw: object) -> Services:
    return Services(tmp_path / "data", "https://nw.example", models, link_secret=SECRET,
                    prices=NoPrices(), **kw)  # type: ignore[arg-type]  # fmt: skip


@pytest.fixture(autouse=True)
def fixed_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nh, "load_table", lambda: TABLE)


def talk(tmp_path: Path, models: FakeModels | None = None, lang: str = "en", **kw: object) -> Chat:
    chat = Chat(tmp_path, services(tmp_path, FakeModels() if models is None else models, **kw))
    onboard(chat)
    chat.store.save_profile(dataclasses.replace(chat.profile, lang=lang))
    chat.bot.download_file = lambda file_id: (chat.bot.downloads.append(file_id), PNG)[1]  # type: ignore[method-assign]
    return chat


@pytest.fixture
def chat(tmp_path: Path) -> Chat:
    return talk(tmp_path)


def photo(chat: Chat, **message: object) -> None:
    sizes = [{"file_id": "small"}, {"file_id": "big"}]
    body = message or {"photo": sizes}
    update = {"update_id": next(_ids), "message": {"message_id": 1, "chat": {"id": CHAT}, **body}}
    from networth.bot.commands import handle_update

    handle_update(update, chat.store, chat.bot, NOW, chat.services)


def last(chat: Chat) -> Message:
    return chat.bot.messages[-1]


def buttons(chat: Chat) -> list[tuple[str, str, str | None]]:
    return [(b.label, b.data, b.url) for row in chat.bot.sent[-1][2] for b in row]


def stored(chat: Chat):
    data = chat.store.holdings_data(USER)
    return from_json(data) if data else None


def expected_lines(chat: Chat, lang: str) -> list[str]:
    report = nh.report_for(USER, chat.store, table=TABLE)
    assert report is not None, "a confirmed list"
    return nh.holdings_lines(report, lang)


def confirm(chat: Chat) -> None:
    photo(chat)
    chat.say("3 growth")
    chat.tap("hd:ok")


@pytest.mark.parametrize("lang", LANGS)
def test_a_photo_becomes_a_confirm_prompt_listing_all_seven(tmp_path: Path, lang: str) -> None:
    chat = talk(tmp_path, lang=lang)
    photo(chat)
    m = last(chat)
    assert m.title == flow.TITLE[lang] and m.footer == ""
    rows = m.body[0].splitlines()
    assert len(rows) == 7
    for n, (row, name) in enumerate(zip(rows, NAMES, strict=True), start=1):
        assert row.startswith(f"{n}. ") and name in row
    assert flow.WHICH_BUCKET[lang].format(n=3) in plain(m)
    assert [d for _, d, _ in buttons(chat)] == ["hd:ok", "hd:fix", "hd:cancel"]
    assert [label for label, _, _ in buttons(chat)] == [
        flow.LOOKS_RIGHT[lang], flow.FIX_A_LINE[lang], flow.CANCEL[lang]]  # fmt: skip
    assert stored(chat) is not None and not stored(chat).confirmed


def test_the_english_rows_carry_units_cost_and_bucket(chat: Chat) -> None:
    photo(chat)
    text = plain(last(chat))
    assert "1. UTI Nifty 50 Index Fund Direct Growth: 1250 units, average cost ₹128.40 (core)" in (
        text)  # fmt: skip
    assert "3. Parag Parikh Flexi Cap Fund Direct Growth: 800 units, average cost ₹68.50\n" in text


def test_a_picture_that_is_not_holdings_goes_to_explain_and_keeps_the_list(tmp_path) -> None:
    chat = talk(tmp_path)
    confirm(chat)
    before = chat.store.holdings_data(USER)
    chat.services = dataclasses.replace(chat.services, models=FakeModels(holdings=False))
    photo(chat)
    assert chat.services.models.images == [PNG]
    assert plain(last(chat)).startswith(explain.CANT_READ["en"])
    assert chat.store.holdings_data(USER) == before


def test_a_picture_that_is_not_holdings_stores_nothing(tmp_path: Path) -> None:
    chat = talk(tmp_path, FakeModels(holdings=False))
    photo(chat)
    assert chat.store.holdings_data(USER) is None


def test_looks_right_with_a_line_unplaced_asks_again(chat: Chat) -> None:
    photo(chat)
    chat.tap("hd:ok")
    assert last(chat).title == flow.TITLE["en"] and not stored(chat).confirmed


@pytest.mark.parametrize("lang", LANGS)
def test_looks_right_gives_the_report_with_every_holdings_line(tmp_path, lang: str) -> None:
    chat = talk(tmp_path, lang=lang)
    confirm(chat)
    m, lines = last(chat), expected_lines(chat, lang)
    assert stored(chat).confirmed
    assert m.title == lines[0] and m.footer == FOOTER[lang]
    text = plain(m)
    for line in lines[:-1]:
        assert line in text, line
    phrase = flow.SENTENCE_END.split(nh.LINES[lang]["label"])[-1]
    assert lines[-1].removesuffix(phrase).strip() in text
    assert text.count(phrase) == (1 if phrase == FOOTER[lang] else 0)
    assert text.endswith(FOOTER[lang])


def test_a_typed_fix_shows_the_prompt_again_and_is_not_sent_to_chat(chat: Chat) -> None:
    photo(chat)
    chat.say("2 units 15")
    assert "2. HDFC Liquid Fund Direct Growth: 15 units" in plain(last(chat))
    assert stored(chat).items[1].units == 15


def test_fix_then_looks_right_reports(chat: Chat) -> None:
    photo(chat)
    chat.say("3 growth")
    assert flow.WHICH_BUCKET["en"].format(n=3) not in plain(last(chat))
    chat.tap("hd:ok")
    assert last(chat).title == expected_lines(chat, "en")[0]


def test_fix_a_line_explains_the_format(chat: Chat) -> None:
    photo(chat)
    chat.tap("hd:fix")
    assert chat.bot.last == flow.HOW_TO_FIX["en"]


def test_cancel_leaves_nothing_stored(chat: Chat) -> None:
    photo(chat)
    chat.tap("hd:cancel")
    assert chat.store.holdings_data(USER) is None
    assert chat.bot.last == flow.CANCELLED["en"]


def test_a_tap_with_nothing_pending_asks_for_a_screenshot(chat: Chat) -> None:
    chat.tap("hd:ok")
    assert chat.bot.last == flow.NO_HOLDINGS["en"]
    assert chat.bot.answers[-1][1] is None, "the tap is answered"


def test_an_unconfirmed_list_never_gives_a_report(tmp_path: Path) -> None:
    chat = talk(tmp_path, FakeModels(intent="holdings"))
    photo(chat)
    chat.say("3 growth")
    chat.say("/holdings")
    assert chat.bot.last == flow.NO_HOLDINGS["en"]
    chat.say("how are my investments doing")
    assert chat.bot.last == flow.NO_HOLDINGS["en"]


def test_holdings_with_no_list_asks_for_a_screenshot(chat: Chat) -> None:
    chat.say("/holdings")
    assert chat.bot.last == flow.NO_HOLDINGS["en"] and buttons(chat) == []


def test_holdings_sends_the_report_with_the_page_button(chat: Chat) -> None:
    confirm(chat)
    chat.say("/holdings")
    assert last(chat).title == expected_lines(chat, "en")[0]
    ((label, _, url),) = buttons(chat)
    assert label == flow.PAGE_BUTTON["en"]
    assert url is not None and url.startswith("https://nw.example/u/")
    assert url.endswith("/holdings")


def test_holdings_has_no_page_button_without_a_public_url(tmp_path: Path) -> None:
    chat = talk(tmp_path)
    chat.services = dataclasses.replace(chat.services, public_url=None)
    confirm(chat)
    chat.say("/holdings")
    assert buttons(chat) == []


def test_holdings_before_setup_asks_to_finish(tmp_path: Path) -> None:
    chat = Chat(tmp_path, services(tmp_path))
    chat.say("/start")
    chat.say("/holdings")
    assert chat.bot.last == "Let's finish setting up first."


@pytest.mark.parametrize("lang", LANGS)
def test_what_should_i_sell_gets_the_decline_and_the_report(tmp_path, lang: str) -> None:
    chat = talk(tmp_path, lang=lang)
    confirm(chat)
    chat.services = dataclasses.replace(chat.services, models=None)
    chat.say("What should I sell?")
    m, lines = last(chat), expected_lines(chat, lang)
    text = plain(m)
    assert text.startswith(nh.LINES[lang]["decline"])
    assert all(line in text for line in lines[1:-1])
    assert m.footer == FOOTER[lang] and text.endswith(FOOTER[lang])


def test_a_hinglish_portfolio_question_is_answered_in_hinglish(tmp_path: Path) -> None:
    chat = talk(tmp_path)
    confirm(chat)
    chat.services = dataclasses.replace(chat.services, models=None)
    chat.say("kya mera portfolio theek hai")
    assert plain(last(chat)).startswith(nh.LINES["hinglish"]["decline"])
    assert last(chat).footer == FOOTER["hinglish"]
    assert "Research, advice nahin." not in plain(last(chat))


def test_an_advice_draft_from_the_writer_falls_back_to_the_decline(tmp_path: Path) -> None:
    models = FakeModels(intent="holdings", writes=["You should sell Tata Motors."] * 2)
    chat = talk(tmp_path, models)
    confirm(chat)
    chat.say("What should I sell?")
    text = plain(last(chat))
    assert text.startswith(nh.LINES["en"]["decline"]) and "Tata Motors" in text
    assert "sell" not in text.lower() and text.count(FOOTER["en"]) == 1


def test_a_fix_typed_after_confirming_goes_to_chat_and_keeps_the_list(chat: Chat) -> None:
    confirm(chat)
    chat.say("1 growth")
    assert stored(chat).confirmed and last(chat).title != flow.TITLE["en"]


def test_a_dollar_list_keeps_every_line_in_its_place(chat: Chat) -> None:
    confirm(chat)
    h = stored(chat)
    usd = dataclasses.replace(h, items=tuple(dataclasses.replace(x, currency="USD")
                                             for x in h.items))  # fmt: skip
    chat.store.save_holdings(USER, nh.model.to_json(usd))
    chat.say("/holdings")
    m, lines = last(chat), expected_lines(chat, "en")
    assert nh.LINES["en"]["not_rupees"] in lines
    assert m.title == lines[0] and m.detail == tuple(lines[len(lines) - len(m.detail) - 1 : -1])
    assert all(line in plain(m) for line in lines[:-1])
