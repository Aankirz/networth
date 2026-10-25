"""Holdings: the screenshot read into a list, the user's confirm, the factual report in three
languages and the /u/{token}/holdings page. No network: the vision answer is the recorded one
for tests/fixtures/holdings/groww_fake.png, and prices come from a fake."""

from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from networth import config, guard
from networth import holdings as nh
from networth.app.services import Services
from networth.app.store import Plan, Profile, Step, Store
from networth.holdings.lines import holdings_lines, money
from networth.holdings.model import (
    Bucket,
    Holding,
    Holdings,
    Kind,
    PriceFrom,
    Source,
    bucket_for,
    from_json,
    to_json,
)
from networth.holdings.prices import price_holdings
from networth.holdings.report import NoHistory, holdings_report, largest_remainder
from networth.holdings.returns import Return, holding_return, total_return, xirr
from networth.llm import OpenAIModels, WireHoldings
from tests.test_links import SECRET, page_path
from tests.test_onboarding import USER, Chat, onboard
from tests.test_sim_web import TABLE, app_with
from tests.test_web import BANNED as WEB_BANNED
from tests.test_web import DISCLAIMER, text
from tests.watcher_fakes import FAKE_ENV

FIXTURES = Path(__file__).parent / "fixtures" / "holdings"
PNG = (FIXTURES / "groww_fake.png").read_bytes()
NOW = dt.datetime(2026, 10, 25, 6, tzinfo=dt.UTC)
LANGS = ("en", "hi", "hinglish")
LABEL = "This is what you hold and what history says about a mix like it."
PATHS = 200


class Recorded:
    """The vision model's recorded answer for groww_fake.png."""

    def read_holdings(self, image: bytes, mime: str, lang: str) -> WireHoldings:
        return WireHoldings.model_validate_json((FIXTURES / "groww_fake_vision.json").read_text())


def lot(name: str = "Example Fund", units: float = 1.0, cost: float = 100.0,
        price: float | None = 121.0, bought: dt.date | None = None, *,
        currency: str = "INR", bucket: Bucket | None = Bucket.CORE) -> Holding:  # fmt: skip
    return Holding(name, units, cost, currency, Kind.MUTUAL_FUND, bought_on=bought, price=price,
                   price_from=PriceFrom.SCREENSHOT, bucket=bucket)  # fmt: skip


def profile(currency: str = "INR") -> Profile:
    return Profile(USER, "telegram", 4242, Step.DONE, "tok", "", "", lang="en",
                   horizon_years=4, monthly_amount=100_000, currency=currency)  # fmt: skip


PLAN = Plan(USER, "balanced", {"safety": 20, "core": 70, "growth": 10}, 20, "")


def fixture_holdings(*, confirmed: bool = True) -> Holdings:
    read = nh.read_screenshot(PNG, "en", reader=Recorded(), user_id=USER, now=NOW)
    items = list(read.items)
    items[2] = dataclasses.replace(items[2], bucket=Bucket.GROWTH)  # the flexi-cap fund
    return dataclasses.replace(read, items=tuple(items), confirmed=confirmed)


def usd_holdings() -> Holdings:
    items = (
        lot("Example Total Market ETF", 10, 123.4, 210.0, currency="USD"),
        lot("Example Treasury Fund", 5, 98.0, 99.5, currency="USD", bucket=Bucket.SAFETY),
    )
    return Holdings(USER, Source.SNAPTRADE, NOW, items, confirmed=True)  # fmt: skip


def report(h: Holdings | None = None, currency: str = "INR"):
    r = holdings_report(h or fixture_holdings(), profile(currency), PLAN, table=TABLE, paths=PATHS)
    assert r is not None, "a confirmed, placed list has a report"
    return r


# --- the data ---


@pytest.mark.parametrize(("name", "kind", "bucket"), [
    ("HDFC Liquid Fund Direct Growth", Kind.MUTUAL_FUND, Bucket.SAFETY),
    ("ICICI Prudential Banking & PSU Debt Fund", Kind.MUTUAL_FUND, Bucket.SAFETY),
    ("SBI Fixed Deposit", Kind.FD, Bucket.SAFETY),
    ("UTI Nifty 50 Index Fund Direct Growth", Kind.MUTUAL_FUND, Bucket.CORE),
    ("Vanguard S&P 500 ETF", Kind.ETF, Bucket.CORE),
    ("Nippon India Pharma Fund", Kind.MUTUAL_FUND, Bucket.GROWTH),
    ("Axis Small Cap Fund", Kind.MUTUAL_FUND, Bucket.GROWTH),
    ("HDFC Bank", Kind.STOCK, Bucket.GROWTH),
    ("Parag Parikh Flexi Cap Fund Direct Growth", Kind.MUTUAL_FUND, None),
    ("Something unlabelled", Kind.OTHER, None),
])  # fmt: skip
def test_the_bucket_table_places_what_it_knows_and_leaves_the_rest_to_the_user(
    name: str, kind: Kind, bucket: Bucket | None
) -> None:
    assert bucket_for(name, kind) is bucket


def test_xirr_matches_a_hand_checked_case() -> None:
    # 100 in on 2021-01-01, 121 out on 2023-01-01: 1.1 squared is 1.21, so 10% a year.
    h = lot(bought=dt.date(2021, 1, 1))
    assert holding_return(h, dt.date(2023, 1, 1)) == Return("xirr", 10.0)
    assert xirr([(dt.date(2021, 1, 1), -100.0), (dt.date(2023, 1, 1), 121.0)]) == pytest.approx(
        0.1, abs=1e-6
    )


def test_the_total_over_two_lots_is_one_xirr() -> None:
    # Both lots grew 10% a year: 100 from 2021 is 121, 100 from 2022 is 110, by 2023.
    items = [lot(bought=dt.date(2021, 1, 1)), lot(price=110.0, bought=dt.date(2022, 1, 1))]
    assert total_return(items, dt.date(2023, 1, 1)) == Return("xirr", 10.0)


def test_no_dates_gives_a_simple_return_labelled_as_such() -> None:
    h = lot(price=120.0)
    assert holding_return(h, dt.date(2026, 10, 25)) == Return("simple", 20.0)
    holdings = Holdings(USER, Source.SCREENSHOT, NOW, (h,), confirmed=True)
    row_line = holdings_lines(report(holdings), "en")[1]
    assert "+20.0% in total, a simple return as no start date was shown" in row_line


def test_under_a_year_is_not_annualised() -> None:
    h = lot(price=105.0, bought=dt.date(2026, 7, 1))
    assert holding_return(h, dt.date(2026, 10, 25)) == Return("short", 5.0)


def test_one_undated_lot_makes_the_total_simple() -> None:
    items = [lot(bought=dt.date(2021, 1, 1)), lot(price=110.0)]
    assert total_return(items, dt.date(2023, 1, 1)) == Return("simple", 15.5)


def test_invested_and_value_are_units_times_cost_and_price() -> None:
    r = report()
    # 1250 x 128.4 + 20.5 x 4720 + 800 x 68.5 + 40 x 2450 + 60 x 910 + 150 x 470 + 25 x 1540
    assert r.invested == 573_660
    assert r.rows[0].value == 202_625  # 1250 x 162.1
    assert r.gain == r.value - r.invested


def test_an_unpriced_holding_is_valued_at_cost() -> None:
    h = Holdings(USER, Source.SCREENSHOT, NOW, (lot(price=None),), confirmed=True)
    row = report(h).rows[0]
    assert (row.invested, row.value, row.gain) == (100, 100, 0)


@pytest.mark.parametrize("weights", [(1.0, 1.0, 1.0), (104_659, 202_625, 343_998), (0, 0, 5)])
def test_mix_percentages_sum_to_exactly_100(weights) -> None:
    assert sum(largest_remainder(weights)) == 100


def test_the_mix_is_by_current_value() -> None:
    assert report().held_pct == (16, 31, 53)


# --- the lines ---


def test_the_gap_is_two_facts_with_no_advice_in_any_language() -> None:
    r = report()
    lines = holdings_lines(r, "en")
    assert (
        "Your plan says 10% single shares or themes. Your holdings are 53% single shares or themes."
        in lines
    )
    for lang in LANGS:
        for line in holdings_lines(r, lang):
            assert not guard.BANNED.search(line), line
            assert not guard.ADVICE.search(line), line


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("currency", ["INR", "USD"])
def test_every_line_passes_the_guard_against_the_report(lang: str, currency: str) -> None:
    r = report(usd_holdings(), "USD") if currency == "USD" else report()
    lines = holdings_lines(r, lang)
    assert lines[-1] == nh.LINES[lang]["label"]
    for line in lines:
        assert guard.check(line, repr(r)).ok, (line, guard.check(line, repr(r)).problems)


def test_the_history_compares_the_held_mix_with_the_saved_plan_only() -> None:
    r = report()
    h = r.history
    assert not isinstance(h, NoHistory)
    assert (h.held.targets_pct, h.plan.targets_pct) == (r.held_pct, (20, 70, 10))
    assert (
        f"In {h.held.hit_limit_pct}% of paths a mix like your holdings fell 20% or more at "
        f"some point. Your saved plan: {h.plan.hit_limit_pct}%."
    ) in holdings_lines(r, "en")


def test_dollars_are_us_grouped_whole_dollars_with_no_history() -> None:
    assert money(1234, "USD") == "$1,234"
    assert money(-1_234_567, "USD") == "−$1,234,567"
    r = report(usd_holdings(), "USD")
    assert r.history is NoHistory.NOT_RUPEES
    lines = holdings_lines(r, "en")
    assert "Put in $1,234, worth $2,100 now, +$866" in lines[1]
    assert "What history says about a mix like this is in rupees only for now." in lines


def test_rupees_use_indian_grouping() -> None:
    assert "In total: put in ₹5,73,660, worth ₹6,51,285 now" in holdings_lines(report(), "en")[8]


# --- prices ---


class FakePrices:
    def __init__(self, quotes: dict[str, tuple[float, str] | Exception]) -> None:
        self.quotes, self.asked = quotes, []

    def quote(self, symbol: str) -> tuple[float, str] | None:
        self.asked.append(symbol)
        q = self.quotes.get(symbol)
        if isinstance(q, Exception):
            raise q
        return q


def test_a_ticker_that_resolves_gets_our_price_and_the_rest_keep_theirs() -> None:
    prices = FakePrices({"RELIANCE.NS": TimeoutError(), "RELIANCE.BO": (2900.0, "INR"),
                         "INFY.NS": (19.5, "USD"), "TATAMOTORS.NS": (700.0, "INR")})  # fmt: skip
    priced = price_holdings(fixture_holdings(), prices, now=NOW)
    by_name = {h.name: h for h in priced.items}
    assert (by_name["Reliance Industries"].price, by_name["Reliance Industries"].price_from) == (
        2900.0, PriceFrom.LOOKED_UP)  # fmt: skip
    assert by_name["Tata Motors"].price_from is PriceFrom.LOOKED_UP
    assert (by_name["Infosys"].price, by_name["Infosys"].price_from) == (
        1612.4,
        PriceFrom.SCREENSHOT,
    )
    assert "UTI Nifty 50 Index Fund Direct Growth" not in " ".join(prices.asked)
    r = report(priced)
    assert "Prices looked up on 25 October 2026: 2 of 7 holdings." in holdings_lines(r, "en")


# --- the confirm flow and the entry points ---


@pytest.fixture
def chat(tmp_path: Path) -> Chat:
    chat = Chat(tmp_path, Services(tmp_path / "data", "https://nw.example", link_secret=SECRET))
    onboard(chat)  # Balanced, ₹1,00,000 a month, 4 years, INR, English
    return chat


def test_the_fake_groww_screenshot_is_read_in_full_and_waits_for_a_confirm(chat: Chat) -> None:
    read = nh.holdings_from_photo(USER, PNG, chat.store, reader=Recorded())
    names = ("UTI Nifty 50 Index Fund", "HDFC Liquid Fund", "Parag Parikh", "Reliance",
             "Tata Motors", "Bank BeES", "Infosys")  # fmt: skip
    assert [n for n in names for x in read.holdings.items if n in x.name] == list(names)
    assert (read.added, read.same) == (7, 0)
    assert read.holdings.unplaced == (3,) and not read.holdings.confirmed


def test_fixing_and_confirming_the_list(chat: Chat) -> None:
    nh.holdings_from_photo(USER, PNG, chat.store, reader=Recorded())
    assert nh.confirm_holdings(USER, chat.store) is None, "line 3 has no kind yet"
    assert nh.fix_line(USER, chat.store, "what should I sell") is None
    assert nh.fix_line(USER, chat.store, "9 units 3") is None
    nh.fix_line(USER, chat.store, "3 growth")
    nh.fix_line(USER, chat.store, "2 units 15")
    nh.fix_line(USER, chat.store, "4 cost 2,500")
    h = nh.fix_line(USER, chat.store, "7 drop")
    assert h is not None and len(h.items) == 6
    assert h.items[1].units == 15 and h.items[3].avg_cost == 2500
    confirmed = nh.confirm_holdings(USER, chat.store)
    assert confirmed is not None and confirmed.confirmed
    message = nh.holdings_message(USER, chat.store, table=TABLE)
    assert message is not None and "Infosys" not in message and LABEL in message
    assert nh.fix_line(USER, chat.store, "1 units 1000") is None, "a confirmed list is kept"


def test_confirm_with_nothing_pending_confirms_nothing(chat: Chat) -> None:
    assert nh.confirm_holdings(USER, chat.store) is None


def test_explain_a_holding_in_plain_words(chat: Chat) -> None:
    chat.store.save_holdings(USER, to_json(fixture_holdings()))
    about = nh.explain_holding(USER, 2, chat.store)
    assert about is not None
    assert about.startswith("Safe money is meant to stay steady")
    assert "2. HDFC Liquid Fund Direct Growth (safe money (liquid, gilt, FD))" in about
    assert not guard.ADVICE.search(about) and not guard.BANNED.search(about)
    assert nh.explain_holding(USER, 8, chat.store) is None


def test_stop_deletes_the_holdings(chat: Chat) -> None:
    chat.store.save_holdings(USER, to_json(fixture_holdings()))
    chat.say("/stop")
    assert chat.store.holdings_data(USER) is None


def _files(*roots: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for root in roots if root.exists()
            for p in root.rglob("*") if p.is_file()}  # fmt: skip


def test_the_image_is_never_written(chat: Chat, tmp_path: Path) -> None:
    repo_data = Path(__file__).parents[1] / "data"
    before = _files(tmp_path, repo_data)
    nh.holdings_from_photo(USER, PNG, chat.store, reader=Recorded())
    after = _files(tmp_path, repo_data)
    encoded = base64.b64encode(PNG)
    new = set(after) - set(before)
    assert not new, new
    for path, content in after.items():
        assert PNG[:64] not in content and encoded[:64] not in content, path
    assert from_json(chat.store.holdings_data(USER) or "").items, "the list itself was stored"


def test_the_vision_call_log_holds_no_image(tmp_path: Path) -> None:
    sent: list[dict] = []
    parsed = Recorded().read_holdings(PNG, "image/png", "en")

    def parse(**request):
        sent.append(request)
        return SimpleNamespace(output_parsed=parsed, usage=None)

    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    cfg = config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)
    log = tmp_path / "llm_calls.jsonl"
    models = OpenAIModels(cfg, log_path=log, client=client)  # type: ignore[arg-type]
    store = Store(tmp_path / "data")
    prompt = nh.holdings_from_photo(USER, PNG, store, reader=models)
    assert len(prompt.holdings.items) == 7
    encoded = base64.b64encode(PNG).decode()
    assert encoded in json.dumps(sent, default=str), "the image went into the request"
    (record,) = [json.loads(x) for x in log.read_text().splitlines()]
    assert record["call"] == "read_holdings" and record["role"] == "vision"
    assert encoded[:64] not in log.read_text()


class Writer:
    def __init__(self, draft: str) -> None:
        self.draft, self.calls = draft, 0

    def write(self, task: str, facts: str, feedback: str | None = None) -> str:
        self.calls += 1
        return self.draft


def test_an_advice_draft_falls_back_to_the_decline_and_the_report(chat: Chat, tmp_path) -> None:
    chat.store.save_holdings(USER, to_json(fixture_holdings()))
    writer = Writer("You should sell Tata Motors.")
    reply = nh.holdings_answer(USER, "what should I sell", chat.store, writer,
                               log_path=tmp_path / "guard.jsonl", table=TABLE)  # fmt: skip
    assert writer.calls == 2
    assert reply.startswith(nh.LINES["en"]["decline"])
    assert reply.endswith(LABEL)
    assert "sell" not in reply.lower()


def test_a_factual_draft_from_the_report_is_sent(chat: Chat, tmp_path) -> None:
    chat.store.save_holdings(USER, to_json(fixture_holdings()))
    draft = "I don't rate holdings. Tata Motors was put in at ₹54,600 and is worth ₹44,541 now."
    reply = nh.holdings_answer(USER, "is tata bad", chat.store, Writer(draft),
                               log_path=None, table=TABLE)  # fmt: skip
    assert reply == draft
    assert guard.check(draft, nh.holdings_source(USER, chat.store, table=TABLE)).ok


def test_no_report_gets_the_screenshot_line(chat: Chat) -> None:
    reply = nh.holdings_answer(USER, "rate my portfolio", chat.store, Writer("x"), log_path=None)
    assert reply == nh.LINES["en"]["no_report"]


# --- the page ---


def holdings_page(chat: Chat):
    return app_with(TABLE, chat.store.path.parent).get(page_path(chat.store) + "/holdings")


def test_the_page_shows_the_report_the_mix_bar_and_the_label(chat: Chat) -> None:
    chat.store.save_holdings(USER, to_json(fixture_holdings()))
    response = holdings_page(chat)
    assert response.status_code == 200
    assert response.headers["X-Robots-Tag"] == "noindex"
    page, words = response.text, text(response.text)
    assert DISCLAIMER in page and LABEL in words
    assert '<svg viewBox="0 0 400' in page and 'role="img"' in page and "<title" in page
    assert (
        "Your plan says 10% single shares or themes. Your holdings are 53% single shares or themes."
        in words
    )
    assert "Parag Parikh Flexi Cap Fund Direct Growth" in words and "₹5,73,660" in words
    assert not WEB_BANNED.search(page) and not guard.BANNED.search(words)


def test_the_page_shows_no_holdings_until_they_are_confirmed(chat: Chat) -> None:
    chat.store.save_holdings(USER, to_json(fixture_holdings(confirmed=False)))
    words = text(holdings_page(chat).text)
    assert "Send a screenshot of your holdings in the bot, then confirm it." in words
    assert "Parag Parikh" not in words


def test_a_bad_link_gets_the_friendly_404(chat: Chat) -> None:
    response = app_with(TABLE, chat.store.path.parent).get("/u/nope.123.abc/holdings")
    assert response.status_code == 404


def bank_bees_row(**changes: str) -> dict:
    """The real Bank BeES row from the Groww screenshot fixture, with fields a broker changes."""
    rows = json.loads((FIXTURES / "groww_fake_vision.json").read_text())["rows"]
    row = next(r for r in rows if r["identifier"] == "BANKBEES")
    return {**row, **changes}


@pytest.mark.parametrize("changes, bucket", [
    ({}, Bucket.GROWTH),
    ({"name": "BANKBEES"}, Bucket.GROWTH),  # a broker screenshot that shows only the ticker
    ({"name": "PSUBNKBEES", "identifier": "PSUBNKBEES"}, Bucket.GROWTH),
    ({"name": "ITBEES", "identifier": "ITBEES"}, Bucket.GROWTH),
    ({"name": "NIFTYBEES", "identifier": "NIFTYBEES"}, Bucket.CORE),
    ({"name": "LIQUIDBEES", "identifier": "LIQUIDBEES"}, Bucket.SAFETY),
    ({"name": "Nippon India ETF Liquid BeES", "identifier": "LIQUIDBEES"}, Bucket.SAFETY),
    ({"name": "GILT5YBEES", "identifier": "GILT5YBEES"}, Bucket.SAFETY),
    ({"name": "ITOT", "identifier": "ITOT", "currency": "USD"}, Bucket.CORE),
    ({"name": "HDFCSML250", "identifier": "HDFCSML250"}, Bucket.GROWTH),
    ({"name": "MON100", "identifier": "MON100"}, Bucket.GROWTH),  # US tech, bought in INR
    ({"name": "MAFANG", "identifier": "MAFANG"}, Bucket.GROWTH),
])  # fmt: skip
def test_an_equity_etf_is_growth_and_a_liquid_or_gilt_etf_is_safety(
    changes: dict, bucket: Bucket
) -> None:
    from networth.holdings.reader import parse_row
    from networth.llm import WireHolding

    holding = parse_row(WireHolding(**bank_bees_row(**changes)))
    assert not isinstance(holding, str)
    assert holding.bucket is bucket
