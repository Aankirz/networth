"""Memory callbacks: a term the user asked about, brought back once when this month's news
uses it.

    terms = asked_terms("what is OFS?")                                    # ["OFS"]
    back = callback_line(store, profile, watcher_db, today, days=60)       # Callback or None

TERMS comes from the Concept column of knowledge/glossary.md, so a term counts only if the
glossary teaches it. The line names a confirmed story title first seen in the last NEWS_DAYS,
and it passes guard.check like every other line, or it is not offered.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from networth import guard
from networth.app.store import Profile, Store
from networth.config import REPO
from networth.watcher.store import Confirmed
from networth.watcher.store import Store as WatcherStore

GLOSSARY: Final = REPO / "knowledge" / "glossary.md"
MIN_TERM_CHARS: Final = 2
NEWS_DAYS: Final = 30
# ponytail: size words split out of "Large / mid / small / micro cap" are everyday English, so
# they would match almost any question. Dropped by hand rather than by a smarter splitter.
NOISE: Final = frozenset({"large", "mid", "small"})
ACRONYM: Final = re.compile(r"\(([^()\s,]+)\)")
ALTERNATIVES: Final = re.compile(r"\s+/\s+|\s+vs\.?\s+|\s*,\s*")


@dataclass(frozen=True)
class Callback:
    term: str
    line: str


def concepts(markdown: str) -> list[str]:
    """The first cell of every row in the glossary's Concept tables."""
    cells: list[str] = []
    in_table = False
    for line in markdown.splitlines():
        if line.startswith("| Concept |"):
            in_table = True
        elif in_table and line.startswith("|") and not line.startswith("|---"):
            cells.append(line.split("|")[1].strip())
        elif not line.startswith("|"):
            in_table = False
    return cells


def split_concept(cell: str) -> list[str]:
    """'Offer for sale (OFS)' -> ['Offer for sale', 'OFS']; 'DRHP / RHP' -> ['DRHP', 'RHP'].
    A parenthesis with spaces or commas is a note ("(e.g. 3x)"), not a name, and is dropped."""
    base = re.sub(r"\([^)]*\)", "", cell)
    parts = [p.strip() for p in (*ALTERNATIVES.split(base), *ACRONYM.findall(cell))]
    return [p for p in parts if len(p) >= MIN_TERM_CHARS and p.casefold() not in NOISE]


def load_terms(path: Path = GLOSSARY) -> tuple[str, ...]:
    found: dict[str, str] = {}
    for cell in concepts(path.read_text(encoding="utf-8")):
        for term in split_concept(cell):
            found.setdefault(term.casefold(), term)
    return tuple(found.values())


def pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(term.casefold())}(?!\w)")


# A brief line stays readable: a headline longer than this is never quoted.
MAX_TITLE: Final = 140
TERMS: Final = load_terms()
PATTERNS: Final = tuple((term, pattern(term)) for term in TERMS)


def asked_terms(text: str) -> list[str]:
    """Glossary terms in the text, without a term that only appears inside a longer one."""
    lowered = text.casefold()
    found = [term for term, p in PATTERNS if p.search(lowered)]
    return [t for t in found
            if not any(t != u and pattern(t).search(u.casefold()) for u in found)]  # fmt: skip


def month_titles(watcher_db: Path, today: dt.date) -> list[tuple[str, tuple[str, ...]]]:
    """(story title, every title to search) for confirmed stories of the last NEWS_DAYS."""
    if not watcher_db.exists():
        return []
    db = WatcherStore.open(watcher_db)
    try:
        articles = db.articles_by_story()
        decisions = db.decisions()
    finally:
        db.close()
    since = today - dt.timedelta(days=NEWS_DAYS)
    return [(d.story.title, (d.story.title, *(a.title for a in articles.get(d.story.id, ()))))
            for d in decisions if isinstance(d.verdict, Confirmed)
            and d.story.first_seen.date() >= since]  # fmt: skip


def callback_line(store: Store, profile: Profile, watcher_db: Path, today: dt.date,
                  days: int) -> Callback | None:  # fmt: skip
    """The newest unused term asked in the last `days` that this month's news uses, as a line
    for the brief."""
    since = (today - dt.timedelta(days=days)).isoformat()
    terms = store.recent_asked_terms(profile.user_id, since)
    stories = month_titles(watcher_db, today) if terms else []
    for term in terms:
        p = pattern(term)
        # Quote the shortest title that holds the term, so the reader sees the connection.
        holding = [
            x
            for _, every in stories
            for x in every
            if len(x) <= MAX_TITLE and p.search(x.casefold())
        ]
        title = min(holding, key=len) if holding else None
        if title is None:
            continue
        line = (f"Earlier you asked what {term} means. It comes up in this month's news: "
                f"{title.rstrip('.')}.")  # fmt: skip
        if guard.check(line, line).ok:
            return Callback(term, line)
    return None
