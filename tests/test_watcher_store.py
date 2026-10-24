"""Opening a watcher file written before the judge answered with a date and a region."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from networth.watcher.store import Store

OLD_SCHEMA = """
CREATE TABLE stories (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, first_seen TEXT NOT NULL,
  type TEXT, cause TEXT, classify_reason TEXT, classified_at TEXT);
CREATE TABLE insights (
  id TEXT PRIMARY KEY, story_id TEXT NOT NULL,
  trigger TEXT NOT NULL CHECK (trigger IN ('news', 'price')), asset TEXT NOT NULL,
  type TEXT NOT NULL, cause TEXT NOT NULL, odds_json TEXT NOT NULL, created_at TEXT NOT NULL);
INSERT INTO stories VALUES
  ('s_old', 'RBI hikes', '2026-10-07T00:00:00+00:00', 'none', '',
   'old news: rbi_hike dated 2026-10-07, before 2026-10-23. r', '2026-10-25T00:00:00+00:00'),
  ('s_hit', 'OPEC cuts', '2026-10-24T00:00:00+00:00', 'oil_supply', 'opec_cut', 'r',
   '2026-10-25T00:00:00+00:00'),
  ('s_new', 'Not judged', '2026-10-24T00:00:00+00:00', NULL, NULL, NULL, NULL);
INSERT INTO insights VALUES
  ('s_hit:XLE:news', 's_hit', 'news', 'XLE', 'oil_supply', 'opec_cut', '{}', '2026-10-25');
"""


def old_file(tmp_path: Path) -> Path:
    path = tmp_path / "watcher.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SCHEMA)
    conn.close()
    return path


def test_an_old_file_is_migrated_and_every_story_is_judged_again(tmp_path: Path) -> None:
    path = old_file(tmp_path)
    store = Store.open(path)
    stories = {s.id: s for s in store.stories()}
    assert {sid: s.classification for sid, s in stories.items()} == dict.fromkeys(stories)
    assert store.insights() == []
    store.close()


def test_opening_a_migrated_file_again_changes_nothing(tmp_path: Path) -> None:
    path = old_file(tmp_path)
    Store.open(path).close()
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE stories SET type = 'none', classify_reason = 'r', "
                     "classified_at = '2026-10-25T01:00:00+00:00', region = 'in'")  # fmt: skip
    store = Store.open(path)
    assert all(s.classification is not None for s in store.stories())
    store.close()
