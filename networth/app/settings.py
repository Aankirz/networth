"""Server settings from the environment, with .env filling gaps for local runs.

    settings = Settings.from_env()

.env is read into a dict and never written into os.environ, so loading it changes nothing for
the rest of the process. A real environment variable always wins over the file. A missing bot
token is allowed: the server still serves /health, and the webhook answers 503.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from networth.config import DATA_DIR

ENV_FILE: Final = Path(__file__).resolve().parents[2] / ".env"
RATES_DB: Final = "base_rates.sqlite"


def read_dotenv(path: Path) -> dict[str, str]:
    """KEY=value lines; blank lines, comments and 'export ' prefixes are skipped."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().removeprefix("export ")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    bot_token: str | None
    webhook_secret: str | None
    public_url: str | None
    link_secret: str | None = None  # LINK_SIGNING_SECRET, signs /u/{token} links

    @property
    def rates_db(self) -> Path:
        """The engine's sqlite. In the container it lives on the /data volume, not in /app."""
        return self.data_dir / RATES_DB

    def __repr__(self) -> str:
        return f"Settings(data_dir={self.data_dir!r}, public_url={self.public_url!r})"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ, dotenv: Path = ENV_FILE) -> Settings:
        env = {**read_dotenv(dotenv), **environ}
        public_url = env.get("PUBLIC_URL", "").rstrip("/") or None
        return cls(
            data_dir=Path(env.get("DATA_DIR") or DATA_DIR),
            bot_token=env.get("TELEGRAM_BOT_TOKEN") or None,
            webhook_secret=env.get("TELEGRAM_WEBHOOK_SECRET") or None,
            public_url=public_url,
            link_secret=env.get("LINK_SIGNING_SECRET") or None,
        )
