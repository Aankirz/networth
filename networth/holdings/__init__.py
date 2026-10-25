"""Holdings: what a user already owns, read from a screenshot, confirmed by them, and reported
as facts next to their own saved plan. Nothing here recommends, ranks or scores.

    prompt = holdings_from_photo(user_id, image_bytes, store, reader=models)  # unconfirmed
    prompt = fix_line(user_id, store, "2 units 15")     # None when it isn't a fix
    reply = confirm_holdings(user_id, store)            # confirmed, or the bucket question
    text = holdings_message(user_id, store)             # the /holdings reply, None until confirmed
    text = explain_holding(user_id, 3, store)           # one holding in plain words
    text = holdings_answer(user_id, "what should I sell", store, models, log_path=guard_log)

The bot wires these to a photo handler, the confirm reply and /holdings. The image is passed
to the reader and dropped: it is never written to disk or a log. Only the holdings list is
stored, and /stop deletes it (Store.save_profile). The broker link, snaptrade_link(user_id,
store), is networth.holdings.snaptrade's, re-exported here.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from networth import guard
from networth.app.store import Store
from networth.holdings.lines import LINES, explain_lines, holdings_lines, lang_of, unit_money
from networth.holdings.lines import units as units_text
from networth.holdings.model import Bucket, Holdings, from_json, to_json
from networth.holdings.prices import Prices, price_holdings
from networth.holdings.reader import HoldingsReader, read_screenshot
from networth.holdings.report import HoldingsReport, holdings_report
from networth.holdings.snaptrade import snaptrade_link
from networth.sim import Lang
from networth.sim.data import MissingSeries, Table, load_table

FIX: Final = re.compile(
    r"^\s*(\d+)\s+(?:(units?|cost)\s+(\d[\d,]*(?:\.\d+)?)|(safety|core|growth|drop))\s*$",
    re.IGNORECASE,
)
HOW_TO_CONFIRM: Final = (
    "Reply yes if this is right, or fix a line, e.g. 2 units 15, 2 cost 450, 2 growth, 2 drop."
)
UNREADABLE: Final = "A clearer screenshot of the holdings screen helps."
NOTHING_PENDING: Final = "Send a screenshot of your holdings first, and I'll read it."
CONFIRMED: Final = "Saved. Type /holdings to see what you hold and what history says about it."
ANSWER_TASK: Final = (
    "The user asked a question about their own holdings. Answer only with facts from the "
    "report below: what they hold, its value, gain and return, their mix next to their saved "
    "plan, and what history says about both. Never recommend, rate, rank, score or compare "
    "holdings, and never say what to do with one. If they ask for any of that, or what to "
    "change, how much to add or take out, or whether to keep or exit something, decline in "
    "one calm sentence and do not answer it indirectly: never set the gap between their "
    "holdings and their plan, or any amount, next to the question as if it were the answer. "
    "Then say /holdings shows their full report. Reply in {language}."
)
LANGUAGES: Final = {"en": "English", "hi": "Hindi, in Devanagari", "hinglish": "Hinglish"}


__all__ = [
    "ConfirmPrompt", "confirm_holdings", "explain_holding", "fix_line", "holdings_answer",
    "holdings_from_photo", "holdings_message", "holdings_source", "report_for", "snaptrade_link",
]  # fmt: skip


class Writer(Protocol):
    def write(self, task: str, facts: str, feedback: str | None = None) -> str: ...


@dataclass(frozen=True)
class ConfirmPrompt:
    text: str
    holdings: Holdings
    unread: tuple[str, ...]


def _pending(user_id: str, store: Store) -> Holdings | None:
    data = store.holdings_data(user_id)
    return from_json(data) if data else None


def _prompt(h: Holdings) -> ConfirmPrompt:
    if not h.items:
        lines = ["I couldn't read any holdings in that screenshot."]
    else:
        lines = ["Here is what I read:"]
        lines += [f"{n}. {x.name}: {units_text(x.units)} units, average cost "
                  f"{unit_money(x.avg_cost, x.currency)}"
                  + (f" ({x.bucket.value})" if x.bucket else "")
                  for n, x in enumerate(h.items, start=1)]  # fmt: skip
    if h.unread:
        lines.append(f"Not read: {'; '.join(h.unread)}.")
    lines += [f"Is line {n} safety, core or growth?" for n in h.unplaced]
    lines.append(HOW_TO_CONFIRM if h.items else UNREADABLE)
    return ConfirmPrompt("\n".join(lines), h, h.unread)


def holdings_from_photo(
    user_id: str,
    image_bytes: bytes,
    store: Store,
    *,
    reader: HoldingsReader,
    prices: Prices | None = None,
) -> ConfirmPrompt:
    """Read, price what resolves, save unconfirmed, and ask the user to check the list."""
    profile = store.get_profile(user_id)
    h = read_screenshot(image_bytes, lang_of(profile.lang if profile else None),
                        reader=reader, user_id=user_id)  # fmt: skip
    if prices is not None:
        h = price_holdings(h, prices)
    store.save_holdings(user_id, to_json(h))
    return _prompt(h)


def _fixed(h: Holdings, m: re.Match[str]) -> Holdings | None:
    n = int(m.group(1))
    if not 1 <= n <= len(h.items):
        return None
    items = list(h.items)
    what, amount, bucket = (m.group(2) or "").lower(), m.group(3), (m.group(4) or "").lower()
    if bucket == "drop":
        del items[n - 1]
    elif bucket:
        items[n - 1] = dataclasses.replace(items[n - 1], bucket=Bucket(bucket))
    else:
        number = float(amount.replace(",", ""))
        if number <= 0:
            return None
        field = "avg_cost" if what == "cost" else "units"
        items[n - 1] = dataclasses.replace(items[n - 1], **{field: number})
    return dataclasses.replace(h, items=tuple(items), confirmed=False)


def fix_line(user_id: str, store: Store, text: str) -> ConfirmPrompt | None:
    """ "2 units 15", "2 cost 450", "2 growth" or "2 drop". None with no list, or not a fix."""
    h, m = _pending(user_id, store), FIX.match(text)
    if h is None or m is None:
        return None
    fixed = _fixed(h, m)
    if fixed is None:
        return None
    store.save_holdings(user_id, to_json(fixed))
    return _prompt(fixed)


def confirm_holdings(user_id: str, store: Store) -> str:
    h = _pending(user_id, store)
    if h is None or not h.items:
        return NOTHING_PENDING
    if h.unplaced:
        return "\n".join(f"Is line {n} safety, core or growth?" for n in h.unplaced)
    store.save_holdings(user_id, to_json(dataclasses.replace(h, confirmed=True)))
    return CONFIRMED


def _table(table: Table | None) -> Table | None:
    if table is not None:
        return table
    try:
        return load_table()
    except MissingSeries:
        return None


def report_for(
    user_id: str,
    store: Store,
    *,
    prices: Prices | None = None,
    table: Table | None = None,
    history: bool = True,
) -> HoldingsReport | None:
    """The report for confirmed holdings, re-priced (and saved) when `prices` is given. None
    without a profile, a plan or confirmed holdings. `table` defaults to data/sim's; with
    history=False nothing is simulated."""
    profile, plan, h = store.get_profile(user_id), store.get_plan(user_id), _pending(user_id, store)
    if profile is None or plan is None or h is None or not h.confirmed:
        return None
    if prices is not None:
        h = price_holdings(h, prices)
        store.save_holdings(user_id, to_json(h))
    return holdings_report(h, profile, plan, table=_table(table) if history else None)


def _lang(user_id: str, store: Store, lang: str | None) -> Lang:
    profile = store.get_profile(user_id)
    return lang_of(lang, profile.lang if profile else None)


def holdings_message(
    user_id: str,
    store: Store,
    *,
    prices: Prices | None = None,
    table: Table | None = None,
    lang: str | None = None,
) -> str | None:
    """The /holdings reply in `lang`, else the user's language."""
    report = report_for(user_id, store, prices=prices, table=table)
    if report is None:
        return None
    return "\n".join(holdings_lines(report, _lang(user_id, store, lang)))


def explain_holding(user_id: str, n: int, store: Store, lang: str | None = None) -> str | None:
    """Line n of the confirmed list in plain words. None for no report or no such line."""
    report = report_for(user_id, store, history=False)
    about = explain_lines(report, n, _lang(user_id, store, lang)) if report else None
    return "\n".join(about) if about else None


def _source(report: HoldingsReport) -> str:
    return "\n".join([repr(report), *holdings_lines(report, "en")])


def holdings_source(user_id: str, store: Store, *, table: Table | None = None) -> str:
    """The text every number in a holdings answer must come from: the report and its lines.
    The same in every language, since the lines' numbers are the same."""
    report = report_for(user_id, store, table=table)
    return _source(report) if report else ""


def holdings_answer(
    user_id: str,
    text: str,
    store: Store,
    models: Writer,
    *,
    log_path: Path | None,
    lang: str | None = None,
    table: Table | None = None,
) -> str:
    """A free-text question about holdings, answered from the report through the guard. A
    draft that fails twice sends the fixed decline and the report itself."""
    chosen = _lang(user_id, store, lang)
    report = report_for(user_id, store, table=table)
    if report is None:
        return LINES[chosen]["no_report"]
    lines = holdings_lines(report, chosen)
    facts = f"{repr(report)}\n\n" + "\n".join(lines) + f"\n\nThe user asked: {text}"
    task = ANSWER_TASK.format(language=LANGUAGES[chosen])
    template = "\n".join([LINES[chosen]["decline"], *lines])
    out = guard.guarded(lambda feedback: models.write(task, facts, feedback), _source(report),
                        template, log_path, "holdings")  # fmt: skip
    return out.text
