"""Holdings on Telegram end to end: a screenshot becomes its worth and a list to check,
That's everything compares it with the plan, a fix or a start over changes the stored list,
/holdings and a holdings question in chat. No network: the vision answer is the recorded one
for groww_fake.png and prices are a fake."""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Sequence
from pathlib import Path

import pytest

from networth import guard
from networth import holdings as nh
from networth.app.services import Services
from networth.bot import holdings as flow
from networth.bot import holdings_words as words
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
def test_a_photo_leads_with_the_worth_and_asks_if_that_is_everything(tmp_path, lang) -> None:
    chat = talk(tmp_path, lang=lang)
    photo(chat)
    m = last(chat)
    assert m.title.startswith(words.GOT_IT[lang].split("{")[0]) and m.footer == ""
    rows = next(b for b in m.body if NAMES[0] in b).splitlines()
    assert len(rows) == 7 and all(any(name in row for row in rows) for name in NAMES)
    assert plain(m).endswith(words.EVERYTHING[lang])
    assert [d for _, d, _ in buttons(chat)] == ["hd:ok", "hd:more", "hd:fix"]
    assert [label for label, _, _ in buttons(chat)] == [
        words.THATS_ALL[lang], words.SEND_MORE[lang], words.WRONG[lang]]  # fmt: skip
    assert stored(chat) is not None and not stored(chat).confirmed


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


def test_thats_everything_with_a_line_unplaced_asks_its_kind(chat: Chat) -> None:
    photo(chat)
    chat.tap("hd:ok")
    assert chat.bot.last == words.WHAT_KIND["en"].format(name=stored(chat).items[2].name)
    assert [d for _, d, _ in buttons(chat)] == [
        "hd:place:3:safety", "hd:place:3:core", "hd:place:3:growth"]  # fmt: skip
    assert not stored(chat).confirmed
    chat.tap("hd:place:3:growth")
    assert stored(chat).confirmed and last(chat).title == words.SAVED["en"]


@pytest.mark.parametrize("lang", LANGS)
def test_thats_everything_compares_with_the_plan(tmp_path, lang: str) -> None:
    chat = talk(tmp_path, lang=lang)
    confirm(chat)
    m = last(chat)
    assert stored(chat).confirmed
    assert m.title == words.SAVED[lang] and m.footer == ""
    assert [d for _, d, _ in buttons(chat)] == ["br:plan", "hd:history"]


def test_holdings_from_the_report_are_unchanged_after_confirming(chat: Chat) -> None:
    confirm(chat)
    chat.say("/holdings")
    m, lines = last(chat), expected_lines(chat, "en")
    assert m.title == lines[0] and all(line in plain(m) for line in lines[:-1])


def test_the_old_typed_fix_still_works_and_is_not_sent_to_chat(chat: Chat) -> None:
    photo(chat)
    chat.say("2 units 15")
    assert stored(chat).items[1].units == 15
    assert last(chat).title.startswith("Got it.")


def test_start_over_leaves_nothing_stored(chat: Chat) -> None:
    photo(chat)
    chat.tap("hd:cancel")
    assert chat.store.holdings_data(USER) is None
    assert chat.bot.last == words.STARTED_OVER["en"]


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
def test_what_should_i_sell_gets_the_plan_gap_and_history_not_a_pick(tmp_path, lang) -> None:
    chat = talk(tmp_path, lang=lang)
    confirm(chat)
    chat.say("What should I sell?")
    m, report = last(chat), nh.report_for(USER, chat.store, table=TABLE)
    text = plain(m)
    assert text.startswith(words.NOT_A_PICK[lang])
    assert all(line in text for line in flow.comparison_lines(report, "Balanced", lang))
    assert all(line in text for line in nh.lines.history_lines(report.history, lang))
    assert guard.check(text, text).ok
    assert m.footer == "" and FOOTER[lang] not in text


def test_a_hinglish_portfolio_question_is_answered_in_hinglish(tmp_path: Path) -> None:
    chat = talk(tmp_path)
    confirm(chat)
    chat.services = dataclasses.replace(chat.services, models=None)
    chat.say("kya mera portfolio theek hai")
    assert plain(last(chat)).startswith(nh.LINES["hinglish"]["decline"])
    assert last(chat).footer == "" and FOOTER["hinglish"] not in plain(last(chat))


def test_a_sell_question_never_reaches_the_writer(tmp_path: Path) -> None:
    models = FakeModels(intent="holdings", writes=["You should sell Tata Motors."] * 2)
    chat = talk(tmp_path, models)
    confirm(chat)
    chat.say("What should I sell?")
    text = plain(last(chat))
    assert text.startswith(words.NOT_A_PICK["en"]) and len(models.writes) == 2
    assert "sell" not in text.lower() and FOOTER["en"] not in text


def test_a_fix_typed_after_confirming_goes_to_chat_and_keeps_the_list(chat: Chat) -> None:
    confirm(chat)
    chat.say("1 growth")
    assert stored(chat).confirmed and not last(chat).title.startswith("Got it.")


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
