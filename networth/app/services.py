"""What a turn needs beyond the user store: where the engine and watcher data live, the models,
the news search and the public URL for links.

    services = Services.from_settings(settings)
    url = services.page_url(profile.link_token, now)   # the user's signed page, or None

Page links point at the site (NETWORTH_SITE_URL) when it is set, else at this server's /u page:
page_base is the one place that decides.

Without an OPENAI_API_KEY or EXA_API_KEY the server still runs: models and search are None, so
every reply falls back to its plain template and tip checks say they can't search right now.
Without KEIKI_API_KEY and KEIKI_AGENT_ID, mail is None and proactive email is not sent.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final

from networth.app import links
from networth.app.settings import RATES_DB, Settings
from networth.app.store import Store
from networth.config import Config, ConfigError, load_config
from networth.holdings.prices import Prices, YahooPrices
from networth.holdings.snaptrade import SnapTrade
from networth.keiki.client import KeikiApi
from networth.keiki.mail import Mail
from networth.llm import ChatModels, OpenAIModels
from networth.ratings.sources import LiveSources, Sources
from networth.watcher.pull import ExaSearch, NewsSearch
from networth.watcher.store import Store as WatcherStore

log = logging.getLogger("networth.app")

WATCHER_DB: Final = "watcher.sqlite"
CALL_LOG: Final = "llm_calls.jsonl"
GUARD_LOG: Final = "guard.jsonl"
TURN_LOG: Final = "keiki_turns.jsonl"


@dataclass(frozen=True)
class Services:
    data_dir: Path
    public_url: str | None = None
    models: ChatModels | None = None
    search: NewsSearch | None = None
    cfg: Config | None = None
    env: Mapping[str, str] = field(default_factory=dict)  # read by Jev for its gateway keys
    link_secret: str | None = None  # signs /u/{token} links
    mail: Mail | None = None  # proactive email through Keiki
    keiki_email: str | None = None  # the inbox address /link replies name
    prices: Prices | None = None  # current prices for holdings; None values them as read
    snaptrade: SnapTrade | None = None  # None builds one from the SnapTrade keys, if set
    site_url: str | None = None  # the dashboard site; page links go there when set
    ratings: Sources | None = None  # rating data for the holdings action plan; None skips it

    @property
    def page_base(self) -> str | None:
        return self.site_url or self.public_url

    def page_url(self, link_token: str, now: dt.datetime) -> str | None:
        """The stored token signed, so issuing a link never retires another one."""
        return links.page_url(self.page_base, link_token, self.link_secret, now)

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

    @property
    def turn_log(self) -> Path:
        return self.data_dir / TURN_LOG

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
        mail = None
        if settings.keiki_api_key and settings.keiki_agent_id:
            mail = Mail(Store(settings.data_dir),
                        KeikiApi(settings.keiki_api_key, settings.keiki_agent_id))  # fmt: skip
        base = cls(settings.data_dir, settings.public_url, link_secret=settings.link_secret,
                   mail=mail, keiki_email=settings.keiki_email,
                   prices=YahooPrices(), site_url=settings.site_url)  # fmt: skip
        base = replace(base, ratings=LiveSources(base.watcher_db))
        try:
            cfg = load_config()
        except ConfigError as exc:
            log.warning("models off, templates only: %s", exc)
            return base
        call_log = settings.data_dir / CALL_LOG
        return replace(base, models=OpenAIModels(cfg, call_log), search=ExaSearch(cfg, call_log),
                       cfg=cfg, env=dict(os.environ))  # fmt: skip
