"""Config validation, the model-id guard, the deadline on a call that never connects, and the
validators that stand between model output and the watcher."""

from __future__ import annotations

import copy
import dataclasses
import threading
import time
import tomllib
from pathlib import Path

import httpx2
import openai
import pytest

from networth import config, net
from networth.engine.model import EventType
from networth.llm import (
    INVALID_OUTPUT,
    ArticleBrief,
    Classified,
    NotAnEvent,
    OpenAIModels,
    StoryBrief,
    _WireClassification,
    _WireGroup,
    _WireGrouping,
    validate_classification,
    validate_grouping,
)

FAKE_ENV = {"OPENAI_API_KEY": "sk-test-not-real", "EXA_API_KEY": "exa-test-not-real"}
DEADLINE_S = 0.5
SLACK_S = 1.0


def raw_config() -> dict:
    return tomllib.loads(config.CONFIG_TOML.read_text(encoding="utf-8"))


def secrets() -> config.Secrets:
    return config.Secrets(FAKE_ENV["OPENAI_API_KEY"], FAKE_ENV["EXA_API_KEY"])


def test_the_shipped_config_parses() -> None:
    cfg = config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)
    assert set(cfg.roles) == set(config.Role)
    assert all(cfg.price_of(r).source_url.startswith("https://") for r in config.Role)
    assert len(cfg.pull.queries) <= cfg.pull.max_queries_per_cycle


def test_secrets_never_show_in_repr() -> None:
    assert FAKE_ENV["OPENAI_API_KEY"] not in repr(secrets())


def test_missing_key_names_the_key(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=sk-x\n")
    with pytest.raises(config.ConfigError, match="EXA_API_KEY is missing from .env"):
        config.load_config(env_path=env, environ={})


def test_keys_are_read_from_the_env_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("# keys\nexport OPENAI_API_KEY='sk-a'\nEXA_API_KEY=\"exa-b\"\n")
    cfg = config.load_config(env_path=env, environ={})
    assert (cfg.secrets.openai_api_key, cfg.secrets.exa_api_key) == ("sk-a", "exa-b")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r["roles"].update(poet=r["roles"]["cheap"]), "unknown role 'poet'"),
        (lambda r: r["prices"].pop("gpt-5.6-sol"), "has no \\[prices\\] entry"),
        (lambda r: r["pull"]["queries"][0].update(types=["moon_landing"]), "unknown event type"),
        (lambda r: r["pull"]["queries"][0].update(region="mars"), "unknown region"),
        (lambda r: r["triggers"]["assets_by_type"].update(alien=["SPY"]), "unknown event type"),
        (lambda r: r["roles"]["cheap"].update(provider="bedrock"), "not supported"),
        (lambda r: r["pull"].update(max_queries_per_cycle=1), "exceed the Exa budget"),
    ],
)
def test_config_rejects_bad_values(mutate, message: str) -> None:
    raw = copy.deepcopy(raw_config())
    mutate(raw)
    with pytest.raises(config.ConfigError, match=message):
        config.parse_config(raw, secrets())


def test_no_model_id_literal_in_python_code() -> None:
    offenders = [
        str(p) for p in Path(config.__file__).parent.rglob("*.py") if "gpt-" in p.read_text()
    ]
    assert offenders == []


def test_price_cost_bills_cached_input_at_the_cached_rate() -> None:
    price = config.Price(2.0, 0.2, 12.0, "https://example.org")
    assert price.cost(1_000_000, 500_000, 100_000) == pytest.approx(1.0 + 0.1 + 1.2)


class NeverConnects(httpx2.BaseTransport):
    """A transport whose connect never completes, like an IPv6 SYN with no answer."""

    def __init__(self) -> None:
        self.release = threading.Event()

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        self.release.wait(60)
        raise httpx2.ConnectError("never connected", request=request)


def fast_deadline_config() -> config.Config:
    cfg = config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)
    http = config.HttpConfig(DEADLINE_S, DEADLINE_S, DEADLINE_S)
    return dataclasses.replace(cfg, http=http)


def test_openai_call_that_never_connects_ends_at_the_deadline_and_is_logged(
    tmp_path: Path,
) -> None:
    cfg = fast_deadline_config()
    transport = NeverConnects()
    client = openai.OpenAI(
        api_key="sk-test-not-real",
        http_client=httpx2.Client(transport=transport),
        max_retries=0,
    )
    log = tmp_path / "llm_calls.jsonl"
    models = OpenAIModels(cfg, log_path=log, client=client)
    start = time.monotonic()
    with pytest.raises(net.CallFailed):
        models.group_articles([ArticleBrief("u1", "P", "t", "s")], [])
    assert time.monotonic() - start < DEADLINE_S + SLACK_S
    transport.release.set()
    (record,) = net.read_records(log)
    assert (record.ok, record.call, record.role) == (False, "group_articles", "cheap")
    assert "DeadlineExceeded" in record.error


ARTICLES = [ArticleBrief(f"https://x.org/{i}", "P", f"t{i}", "") for i in (1, 2, 3)]
SHORT = {"a1": ARTICLES[0].id, "a2": ARTICLES[1].id, "a3": ARTICLES[2].id}
OPEN = [StoryBrief("s_old", "older story")]


def wire(*groups: tuple[str, list[str]]) -> _WireGrouping:
    return _WireGrouping(groups=[_WireGroup(existing_story_id=s, title="t", article_ids=ids)
                                 for s, ids in groups])  # fmt: skip


def test_grouping_maps_short_ids_back_and_keeps_existing_stories() -> None:
    out = validate_grouping(wire(("s_old", ["a1"]), ("", ["a2", "a3"])), ARTICLES, OPEN, SHORT)
    assert out.fallback_reason is None
    assert [(g.existing_story_id, g.article_ids) for g in out.groups] == [
        ("s_old", (ARTICLES[0].id,)),
        (None, (ARTICLES[1].id, ARTICLES[2].id)),
    ]


@pytest.mark.parametrize(
    "bad",
    [
        wire(("", ["a1", "a2"])),  # a3 missing
        wire(("", ["a1", "a2"]), ("", ["a2", "a3"])),  # a2 twice
        wire(("", ["a1", "a2", "a3", "a9"])),  # unknown article
        wire(("s_nope", ["a1", "a2", "a3"])),  # unknown story
        None,
    ],
)
def test_bad_grouping_falls_back_to_one_story_per_article(bad) -> None:
    out = validate_grouping(bad, ARTICLES, OPEN, SHORT)
    assert out.fallback_reason
    assert [g.article_ids for g in out.groups] == [(a.id,) for a in ARTICLES]


ALLOWED = {EventType.RBI_HIKE: ("inflation",), EventType.FED_CUT: ("growth_slowdown",)}


def test_classification_accepts_an_allowed_type_and_cause() -> None:
    out = validate_classification(
        _WireClassification(type="rbi_hike", cause="inflation", reason="r"), ALLOWED
    )
    assert out == Classified(EventType.RBI_HIKE, "inflation", "r")


@pytest.mark.parametrize(
    ("type_", "cause"), [("rbi_hike", "growth_slowdown"), ("moon_landing", ""), ("oil_supply", "")]
)
def test_classification_outside_the_table_is_none(type_: str, cause: str) -> None:
    out = validate_classification(_WireClassification(type=type_, cause=cause, reason="r"), ALLOWED)
    assert out == NotAnEvent(INVALID_OUTPUT)


def test_classification_none_keeps_the_model_reason() -> None:
    out = validate_classification(
        _WireClassification(type="none", cause="", reason="commentary"), ALLOWED
    )
    assert out == NotAnEvent("commentary")
