"""Holdings: what a user already owns, read from a screenshot, confirmed by them, and reported
as facts next to their own saved plan. Nothing here recommends, ranks or scores.

    read = holdings_from_photo(user_id, image_bytes, store, reader=models)  # unconfirmed
    h = start_fix(user_id, store, 2)                    # line 2 is the one being corrected
    h = correct(user_id, store, "15 shares")            # None when the words aren't a fix
    h = fix_line(user_id, store, "2 units 15")          # the old typed syntax, kept as a fallback
    h = confirm_holdings(user_id, store)                # None while a line has no bucket
    text = holdings_message(user_id, store)             # the /holdings reply, None until confirmed
    text = explain_holding(user_id, 3, store)           # one holding in plain words
    text = holdings_answer(user_id, "what should I sell", store, models, log_path=guard_log)

A second screenshot adds to a list still waiting for its confirm: a holding already on it (the
same ticker, else the same name) is updated, never listed twice. The bot wires these to a photo
handler, the confirm buttons and /holdings. The image is passed
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
from networth.holdings.lines import LINES, explain_lines, holdings_lines, lang_of
from networth.holdings.model import Bucket, Holding, Holdings, from_json, to_json
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
NUMBER: Final = r"(\d[\d,]*(?:\.\d+)?)"
SHARES: Final = re.compile(rf"{NUMBER}\s*(?:shares?|units?|qty|शेयर|यूनिट)", re.IGNORECASE)
AVERAGE: Final = re.compile(
    rf"(?:avg|average|cost|price|औसत|लागत)\D{{0,8}}{NUMBER}|{NUMBER}\s*(?:avg|average)",
    re.IGNORECASE,
)
REMOVE: Final = re.compile(r"\b(?:remove|delete|drop|hatao|hata do|nikalo|nikal do)\b|हटा",
                           re.IGNORECASE)  # fmt: skip
BARE: Final = re.compile(rf"^\s*{NUMBER}\s*$")
SPACES: Final = re.compile(r"\s+")
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
    "Read", "confirm_holdings", "correct", "explain_holding", "fix_line", "holdings_answer",
    "holdings_from_photo", "holdings_message", "holdings_source", "pending", "place", "report_for",
    "snaptrade_link", "start_fix",
]  # fmt: skip


class Writer(Protocol):
    def write(self, task: str, facts: str, feedback: str | None = None) -> str: ...


@dataclass(frozen=True)
class Read:
    """The list after a screenshot, and what this screenshot added to a list already waiting."""

    holdings: Holdings
    added: int
    same: int  # rows already on the list, updated in place


def _pending(user_id: str, store: Store) -> Holdings | None:
    data = store.holdings_data(user_id)
    return from_json(data) if data else None


def pending(user_id: str, store: Store) -> Holdings | None:
    """The stored list while it waits for the user's confirm, else None."""
    h = _pending(user_id, store)
    return h if h is not None and not h.confirmed else None


def _key(x: Holding) -> str:
    return (x.identifier or SPACES.sub(" ", x.name)).strip().lower()


def _merged(before: Holdings | None, read: Holdings) -> Read:
    """read alone, or read added to a list still waiting for its confirm."""
    if before is None or before.confirmed or not read.items or before.currency != read.currency:
        return Read(read, len(read.items), 0)
    items, at = list(before.items), {_key(x): i for i, x in enumerate(before.items)}
    for x in read.items:
        if _key(x) in at:
            items[at[_key(x)]] = x
        else:
            at[_key(x)] = len(items)
            items.append(x)
    same = len(before.items) + len(read.items) - len(items)
    merged = dataclasses.replace(read, items=tuple(items), listed=max(before.listed, read.listed))
    return Read(merged, len(read.items) - same, same)


def holdings_from_photo(
    user_id: str,
    image_bytes: bytes,
    store: Store,
    *,
    reader: HoldingsReader,
    prices: Prices | None = None,
) -> Read:
    """Read, price what resolves, add to any list still waiting, and save it unconfirmed. An
    image with no holdings in it changes nothing stored."""
    profile = store.get_profile(user_id)
    h = read_screenshot(image_bytes, lang_of(profile.lang if profile else None),
                        reader=reader, user_id=user_id)  # fmt: skip
    if prices is not None:
        h = price_holdings(h, prices)
    read = _merged(pending(user_id, store), h)
    if read.holdings.items:
        store.save_holdings(user_id, to_json(read.holdings))
    return read


def _save(user_id: str, store: Store, h: Holdings) -> Holdings:
    store.save_holdings(user_id, to_json(h))
    return h


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
    return dataclasses.replace(h, items=tuple(items), confirmed=False, fixing=0)


def fix_line(user_id: str, store: Store, text: str) -> Holdings | None:
    """The old typed syntax, "2 units 15", "2 cost 450", "2 growth" or "2 drop", kept as a
    fallback; the user is never shown it. None with no list waiting, or not a fix."""
    h, m = pending(user_id, store), FIX.match(text)
    fixed = _fixed(h, m) if h is not None and m is not None else None
    return _save(user_id, store, fixed) if fixed is not None else None


def start_fix(user_id: str, store: Store, n: int) -> Holdings | None:
    """Line n is the one the user is correcting; their next words say how."""
    h = pending(user_id, store)
    if h is None or not 1 <= n <= len(h.items):
        return None
    return _save(user_id, store, dataclasses.replace(h, fixing=n))


def _number(text: str) -> float | None:
    number = float(text.replace(",", ""))
    return number if number > 0 else None


def _corrected(x: Holding, text: str) -> Holding | None | bool:
    """The holding with the change in the words, False to remove it, None when unclear."""
    if REMOVE.search(text):
        return False
    if (m := AVERAGE.search(text)) and (cost := _number(m.group(1) or m.group(2))):
        x = dataclasses.replace(x, avg_cost=cost)
        text = text[: m.start()] + text[m.end() :]
        changed = True
    else:
        changed = False
    if (m := SHARES.search(text) or BARE.match(text)) and (count := _number(m.group(1))):
        return dataclasses.replace(x, units=count)
    return x if changed else None


def correct(user_id: str, store: Store, text: str) -> Holdings | None:
    """The line being corrected, changed by plain words: "15 shares", "average 450" or "remove
    it". None when no line is being corrected or the words don't say a change."""
    h = pending(user_id, store)
    if h is None or not 1 <= h.fixing <= len(h.items):
        return None
    changed = _corrected(h.items[h.fixing - 1], text)
    if changed is None:
        return None
    items = list(h.items)
    if changed is False:
        del items[h.fixing - 1]
    else:
        items[h.fixing - 1] = changed
    return _save(user_id, store, dataclasses.replace(h, items=tuple(items), fixing=0))


def place(user_id: str, store: Store, n: int, bucket: Bucket) -> Holdings | None:
    """The user says what kind line n is."""
    h = pending(user_id, store)
    if h is None or not 1 <= n <= len(h.items):
        return None
    items = list(h.items)
    items[n - 1] = dataclasses.replace(items[n - 1], bucket=bucket)
    return _save(user_id, store, dataclasses.replace(h, items=tuple(items), fixing=0))


def confirm_holdings(user_id: str, store: Store) -> Holdings | None:
    """The list, confirmed; None with no list waiting or a line still without a bucket."""
    h = pending(user_id, store)
    if h is None or not h.items or h.unplaced:
        return None
    return _save(user_id, store, dataclasses.replace(h, confirmed=True, fixing=0))


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
