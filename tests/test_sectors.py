"""The sector board: moves from index closes, the confirmed stories behind each."""

from __future__ import annotations

from networth.bot.message import plain
from networth.sectors import BY_KEY, board, board_message, stories_for
from tests.ratings_fakes import NOW, FakeSources, seen


def test_each_sector_has_its_moves_source_and_page() -> None:
    card = board(FakeSources(), NOW, "https://nw.test")
    assert card["type"] == "sectors" and card["currency"] == "INR" and card["note"] is None
    assert [r["key"] for r in card["rows"]] == list(BY_KEY)
    for r in card["rows"]:
        assert r["day"][0] in "+-" and r["week"][0] in "+-" and r["month"][0] in "+-"
        assert r["source"]["name"] and r["source"]["as_of"]
        assert r["url"] == f"https://nw.test/r/sector-{r['key']}"


def test_stories_match_by_word_or_event_type_newest_first_at_most_three() -> None:
    stories = (seen("RBI holds repo rate", "2026-10-20"), seen("Banks rally", "2026-10-22"),
               seen("Lender fined", "2026-10-21"), seen("Bank stress", "2026-10-19", "bank_stress"),
               seen("Fitness app launches", "2026-10-23"))  # fmt: skip
    got = stories_for(BY_KEY["bank"], stories)
    assert [s.title for s in got] == ["Banks rally", "Lender fined", "RBI holds repo rate"]


def test_it_matches_the_capital_word_only() -> None:
    stories = (seen("IT stocks slide on visa curbs"), seen("Why it matters for markets"))
    assert [s.title for s in stories_for(BY_KEY["it"], stories)] == [
        "IT stocks slide on visa curbs"
    ]


def test_the_board_shows_its_news_and_says_when_the_watcher_is_missing() -> None:
    card = board(FakeSources(stories=(seen("Steel prices jump on tariff"),)), NOW)
    metal = next(r for r in card["rows"] if r["key"] == "metal")
    assert metal["stories"][0]["publishers"] == ["reuters.com", "mint.com"]
    text = plain(board_message(card, "https://nw.test"))
    assert "Steel prices jump on tariff (reuters.com, mint.com)" in text
    assert "https://nw.test/r/sectors" in text
    assert "advice" not in text.lower()
    blind = board(FakeSources(stories=None), NOW)
    assert "aren't available" in blind["note"]
