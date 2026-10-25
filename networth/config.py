"""Runtime config: networth/config.toml plus the two API keys, parsed once into a typed Config.

    cfg = load_config()

Everything is validated here, so the rest of the code trusts these types. A missing key, an
unknown role, type, region or provider, or a model with no price raises ConfigError with a
message that names the problem. Entry points print that message and exit 2.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from networth.engine.model import EventType, Region

REPO: Final = Path(__file__).resolve().parents[1]
CONFIG_TOML: Final = Path(__file__).with_name("config.toml")
ENV_FILE: Final = REPO / ".env"
DATA_DIR: Final = REPO / "data"

REQUIRED_KEYS: Final = ("OPENAI_API_KEY", "EXA_API_KEY")
REASONING_EFFORTS: Final = frozenset({"none", "minimal", "low", "medium", "high", "xhigh"})
TOKENS_PER_PRICE_UNIT: Final = 1_000_000


class ConfigError(Exception):
    """The config or .env is unusable. The message is safe to print: it never holds a key."""


class Role(StrEnum):
    CHEAP = "cheap"
    JUDGE = "judge"
    WRITER = "writer"
    VISION = "vision"


Provider = Literal["openai"]


@dataclass(frozen=True)
class RoleConfig:
    provider: Provider
    model: str
    reasoning_effort: str
    max_output_tokens: int


@dataclass(frozen=True)
class Price:
    """USD per 1M tokens. cached_per_m applies to the cached part of the input."""

    input_per_m: float
    cached_per_m: float
    output_per_m: float
    source_url: str

    def cost(self, input_tokens: int, cached_tokens: int, output_tokens: int) -> float:
        fresh = input_tokens - cached_tokens
        usd = fresh * self.input_per_m + cached_tokens * self.cached_per_m
        return (usd + output_tokens * self.output_per_m) / TOKENS_PER_PRICE_UNIT


@dataclass(frozen=True)
class HttpConfig:
    exa_deadline_s: float
    openai_deadline_s: float
    connect_timeout_s: float
    prices_deadline_s: float


@dataclass(frozen=True)
class ConfirmConfig:
    min_publishers: int
    window_hours: int
    primary_domains: tuple[str, ...]
    primary_host_prefixes: tuple[str, ...]
    wire_agencies: Mapping[str, tuple[str, ...]]  # agency name -> byline markers
    publisher_aliases: Mapping[str, str]  # registrable host -> publisher name


@dataclass(frozen=True)
class Query:
    types: tuple[EventType, ...]
    region: Region
    text: str
    include_domains: tuple[str, ...]
    category: str  # "" sends no category, so official pages that are not "news" still match


@dataclass(frozen=True)
class PullConfig:
    lookback_hours: int
    results_per_query: int
    max_queries_per_cycle: int
    queries: tuple[Query, ...]


@dataclass(frozen=True)
class PriceWatch:
    asset: str
    benchmark: str | None  # None measures the raw return


@dataclass(frozen=True)
class TriggerConfig:
    price_multiple: float
    vol_window_days: int
    assets_by_type: Mapping[EventType, tuple[str, ...]]
    price_watch: tuple[PriceWatch, ...]


@dataclass(frozen=True)
class ProductConfig:
    use_jev_for_intent: bool  # set from the measured Jev vs cheap-model accuracy
    jev_min_confidence: float  # below this Jev's pick is ignored and the model decides
    jev_deadline_s: float
    alert_min_episodes: int
    alert_min_gap: float  # |hit rate - baseline| an alert needs
    alert_max_per_month: int
    tip_lookback_days: int
    chat_max_per_hour: int  # paid chat answers per user per rolling hour
    watch_max_active: int  # standing watches one user may hold at once
    watch_max_per_month: int  # watch messages one user may get in a calendar month
    link_code_minutes: int  # how long a /link code works
    memory_days: int  # how far back an asked term may come back in a brief


@dataclass(frozen=True)
class Secrets:
    openai_api_key: str = field(repr=False)
    exa_api_key: str = field(repr=False)


@dataclass(frozen=True)
class Config:
    roles: Mapping[Role, RoleConfig]
    prices: Mapping[str, Price]
    http: HttpConfig
    confirm: ConfirmConfig
    pull: PullConfig
    group_batch_size: int
    max_judge_calls_per_cycle: int
    event_max_age_days: int  # an event older than this, on the cycle's own date, is old news
    triggers: TriggerConfig
    product: ProductConfig
    secrets: Secrets

    def price_of(self, role: Role) -> Price:
        return self.prices[self.roles[role].model]


def _table(raw: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = raw.get(key)
    if not isinstance(value, Mapping):
        raise ConfigError(f"config: [{key}] is missing")
    return value


def _get[T](raw: Mapping[str, object], key: str, kind: type[T], where: str) -> T:
    value = raw.get(key)
    if kind is float and isinstance(value, int) and not isinstance(value, bool):
        value = float(value)
    if not isinstance(value, kind) or isinstance(value, bool) and kind is not bool:
        raise ConfigError(f"config: {where}.{key} must be a {kind.__name__}")
    return value


def _strs(raw: Mapping[str, object], key: str, where: str, default: tuple = ()) -> tuple[str, ...]:
    value = raw.get(key, list(default))
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"config: {where}.{key} must be a list of strings")
    return tuple(value)


def _event_type(value: str, where: str) -> EventType:
    try:
        return EventType(value)
    except ValueError:
        raise ConfigError(f"config: {where} has unknown event type {value!r}") from None


def _roles(raw: Mapping[str, object]) -> dict[Role, RoleConfig]:
    roles: dict[Role, RoleConfig] = {}
    for name, body in _table(raw, "roles").items():
        try:
            role = Role(name)
        except ValueError:
            raise ConfigError(f"config: unknown role {name!r}; one of {list(Role)}") from None
        if not isinstance(body, Mapping):
            raise ConfigError(f"config: [roles.{name}] must be a table")
        where = f"roles.{name}"
        provider = _get(body, "provider", str, where)
        if provider != "openai":
            raise ConfigError(f"config: {where}.provider {provider!r} is not supported")
        effort = _get(body, "reasoning_effort", str, where)
        if effort not in REASONING_EFFORTS:
            raise ConfigError(f"config: {where}.reasoning_effort {effort!r} is not one of "
                              f"{sorted(REASONING_EFFORTS)}")  # fmt: skip
        roles[role] = RoleConfig(
            "openai",
            _get(body, "model", str, where),
            effort,
            _get(body, "max_output_tokens", int, where),
        )
    missing = [r.value for r in Role if r not in roles]
    if missing:
        raise ConfigError(f"config: roles missing: {', '.join(missing)}")
    return roles


def _prices(raw: Mapping[str, object], roles: Mapping[Role, RoleConfig]) -> dict[str, Price]:
    prices: dict[str, Price] = {}
    for model, body in _table(raw, "prices").items():
        if not isinstance(body, Mapping):
            raise ConfigError(f"config: [prices.{model}] must be a table")
        where = f"prices.{model}"
        prices[model] = Price(
            _get(body, "input_per_m", float, where),
            _get(body, "cached_per_m", float, where),
            _get(body, "output_per_m", float, where),
            _get(body, "source_url", str, where),
        )
    for role, rc in roles.items():
        if rc.model not in prices:
            raise ConfigError(f"config: model {rc.model!r} for role {role} has no [prices] entry")
    return prices


def _confirm(raw: Mapping[str, object]) -> ConfirmConfig:
    t = _table(raw, "confirm")
    wires = t.get("wire_agencies", {})
    aliases = t.get("publisher_aliases", {})
    if not isinstance(wires, Mapping) or not isinstance(aliases, Mapping):
        raise ConfigError("config: confirm.wire_agencies and publisher_aliases must be tables")
    return ConfirmConfig(
        _get(t, "min_publishers", int, "confirm"),
        _get(t, "window_hours", int, "confirm"),
        tuple(d.lower() for d in _strs(t, "primary_domains", "confirm")),
        tuple(p.lower() for p in _strs(t, "primary_host_prefixes", "confirm")),
        {name: _strs(wires, name, "confirm.wire_agencies") for name in wires},
        {str(host).lower(): str(name) for host, name in aliases.items()},
    )


def _query(body: object, i: int) -> Query:
    where = f"pull.queries[{i}]"
    if not isinstance(body, Mapping):
        raise ConfigError(f"config: {where} must be a table")
    types = tuple(_event_type(v, where) for v in _strs(body, "types", where))
    if not types:
        raise ConfigError(f"config: {where}.types is empty")
    region = _get(body, "region", str, where)
    try:
        parsed_region = Region(region)
    except ValueError:
        raise ConfigError(f"config: {where} has unknown region {region!r}") from None
    category = body.get("category", "news")
    if not isinstance(category, str):
        raise ConfigError(f"config: {where}.category must be a string")
    return Query(
        types,
        parsed_region,
        _get(body, "text", str, where),
        _strs(body, "include_domains", where),
        category,
    )


def _pull(raw: Mapping[str, object]) -> PullConfig:
    t = _table(raw, "pull")
    queries = t.get("queries", [])
    if not isinstance(queries, list):
        raise ConfigError("config: [[pull.queries]] must be an array of tables")
    pull = PullConfig(
        _get(t, "lookback_hours", int, "pull"),
        _get(t, "results_per_query", int, "pull"),
        _get(t, "max_queries_per_cycle", int, "pull"),
        tuple(_query(q, i) for i, q in enumerate(queries)),
    )
    if len(pull.queries) > pull.max_queries_per_cycle:
        raise ConfigError(f"config: {len(pull.queries)} queries exceed the Exa budget of "
                          f"{pull.max_queries_per_cycle} per cycle")  # fmt: skip
    return pull


def _triggers(raw: Mapping[str, object]) -> TriggerConfig:
    t = _table(raw, "triggers")
    by_type = _table(t, "assets_by_type")
    watch = t.get("price_watch", [])
    if not isinstance(watch, list) or not all(isinstance(w, Mapping) for w in watch):
        raise ConfigError("config: [[triggers.price_watch]] must be an array of tables")
    return TriggerConfig(
        _get(t, "price_multiple", float, "triggers"),
        _get(t, "vol_window_days", int, "triggers"),
        {
            _event_type(k, "triggers.assets_by_type"): _strs(by_type, k, "triggers.assets_by_type")
            for k in by_type
        },  # fmt: skip
        tuple(
            PriceWatch(
                _get(w, "asset", str, "triggers.price_watch"),
                w.get("benchmark") if isinstance(w.get("benchmark"), str) else None,
            )
            for w in watch
        ),
    )


def _product(raw: Mapping[str, object]) -> ProductConfig:
    t = _table(raw, "product")
    return ProductConfig(
        _get(t, "use_jev_for_intent", bool, "product"),
        _get(t, "jev_min_confidence", float, "product"),
        _get(t, "jev_deadline_s", float, "product"),
        _get(t, "alert_min_episodes", int, "product"),
        _get(t, "alert_min_gap", float, "product"),
        _get(t, "alert_max_per_month", int, "product"),
        _get(t, "tip_lookback_days", int, "product"),
        _get(t, "chat_max_per_hour", int, "product"),
        _get(t, "watch_max_active", int, "product"),
        _get(t, "watch_max_per_month", int, "product"),
        _get(t, "link_code_minutes", int, "product"),
        _get(t, "memory_days", int, "product"),
    )


def read_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE lines; blank lines, comments and an optional `export ` prefix are ignored,
    one layer of matching quotes is stripped."""
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_secrets(env_path: Path, environ: Mapping[str, str]) -> Secrets:
    file_values = read_env_file(env_path)
    found: dict[str, str] = {}
    for key in REQUIRED_KEYS:
        value = (environ.get(key) or file_values.get(key) or "").strip()
        if not value:
            raise ConfigError(f"{key} is missing from .env")
        found[key] = value
    return Secrets(found["OPENAI_API_KEY"], found["EXA_API_KEY"])


def parse_config(raw: Mapping[str, object], secrets: Secrets) -> Config:
    roles = _roles(raw)
    group = _table(raw, "group")
    classify = _table(raw, "classify")
    return Config(
        roles=roles,
        prices=_prices(raw, roles),
        http=HttpConfig(
            *(
                _get(_table(raw, "http"), k, float, "http")
                for k in (
                    "exa_deadline_s",
                    "openai_deadline_s",
                    "connect_timeout_s",
                    "prices_deadline_s",
                )
            )
        ),  # fmt: skip
        confirm=_confirm(raw),
        pull=_pull(raw),
        group_batch_size=_get(group, "batch_size", int, "group"),
        max_judge_calls_per_cycle=_get(classify, "max_judge_calls_per_cycle", int, "classify"),
        event_max_age_days=_get(classify, "event_max_age_days", int, "classify"),
        triggers=_triggers(raw),
        product=_product(raw),
        secrets=secrets,
    )


def load_config(
    path: Path = CONFIG_TOML,
    env_path: Path = ENV_FILE,
    environ: Mapping[str, str] | None = None,
) -> Config:
    """Keys come from the environment first, then from the .env file."""
    secrets = load_secrets(env_path, os.environ if environ is None else environ)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"config: cannot read {path}: {exc}") from None
    return parse_config(raw, secrets)
