"""/sectors on Telegram: the board in plain words, its stories, and the sectors with no data."""

from __future__ import annotations

from pathlib import Path

import pytest

from networth.bot import sectors_cmd
from tests.ratings_fakes import FakeSources, seen
from tests.test_onboarding import Chat, onboard


@pytest.fixture
def room(tmp_path: Path) -> Chat:
    return Chat(tmp_path)


class OneDown(FakeSources):
    def closes(self, ticker: str, period: str = "15y"):  # noqa: ANN201 - Closes | None
        return None if ticker == "^CNXIT" else super().closes(ticker, period)


def test_sectors_shows_each_move_its_stories_and_names_the_sector_with_no_data(
    room: Chat, monkeypatch: pytest.MonkeyPatch
) -> None:
    stories = (seen("RBI holds repo rate"),)
    monkeypatch.setattr(sectors_cmd, "SOURCES", lambda services: OneDown(stories=stories))
    onboard(room)
    room.say("/sectors")
    text = room.bot.last
    assert "Bank " in text and "today" in text
    assert "RBI holds repo rate (reuters.com, mint.com)" in text
    assert "No prices for IT right now." in text
    assert "IT +" not in text and "IT -" not in text  # no number for a sector it couldn't read
    assert "advice" not in text.lower()
