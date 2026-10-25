"""What a turn needs beyond the user store: where the engine and watcher data live, the models,
the news search and the public URL for links.

    services = Services.from_settings(settings)

Without an OPENAI_API_KEY or EXA_API_KEY the server still runs: models and search are None, so
every reply falls back to its plain template and tip checks say they can't search right now.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from networth.app.settings import RATES_DB, Settings
from networth.config import Config, ConfigError, load_config
from networth.llm import ChatModels, OpenAIModels
from networth.watcher.pull import ExaSearch, NewsSearch
from networth.watcher.store import Store as WatcherStore

log = logging.getLogger("networth.app")

WATCHER_DB: Final = "watcher.sqlite"
CALL_LOG: Final = "llm_calls.jsonl"
GUARD_LOG: Final = "guard.jsonl"


@dataclass(frozen=True)
class Services:
    data_dir: Path
    public_url: str | None = None
    models: ChatModels | None = None
    search: NewsSearch | None = None
    cfg: Config | None = None
    env: Mapping[str, str] = field(default_factory=dict)  # read by Jev for its gateway keys
    link_secret: str | None = None  # signs /u/{token} links

    @property
    def rates_db(self) -> Path:
        return self.data_dir / RATES_DB

    @property
    def watcher_db(self) -> Path:
        return self.data_dir / WATCHER_DB

    @property
    def call_log(self) -> Path:
        return self.data_dir / CALL_LOG

    @property
    def guard_log(self) -> Path:
        return self.data_dir / GUARD_LOG

    def last_news_check(self) -> dt.datetime | None:
        """When the newest watcher cycle finished, if one ever ran."""
        if not self.watcher_db.exists():
            return None
        store = WatcherStore.open(self.watcher_db)
        try:
            cycle = store.latest_cycle()
        finally:
            store.close()
        return cycle.finished_at if cycle else None

    @classmethod
    def from_settings(cls, settings: Settings) -> Services:
        try:
            cfg = load_config()
        except ConfigError as exc:
            log.warning("models off, templates only: %s", exc)
            return cls(settings.data_dir, settings.public_url, link_secret=settings.link_secret)
        call_log = settings.data_dir / CALL_LOG
        return cls(settings.data_dir, settings.public_url, OpenAIModels(cfg, call_log),
                   ExaSearch(cfg, call_log), cfg, dict(os.environ),
                   settings.link_secret)  # fmt: skip
