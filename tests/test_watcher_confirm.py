"""Pull, grouping and the confirmation rule on fixture articles."""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

import pytest

from networth import config
from networth.watcher import group
from networth.watcher.pull import origin_of, pull
from networth.watcher.store import Article, Confirmed, Rejected, Store, normalize_url
from tests.watcher_fakes import FAKE_ENV, NOW, FakeModels, FakeSearch, story_labels

LOOKBACK = dt.timedelta(hours=48)


@pytest.fixture
def cfg() -> config.Config:
    return config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)


@pytest.fixture
def store(tmp_path: Path):
    s = Store.open(tmp_path / "watcher.sqlite")
    yield s
    s.close()


def verdicts_by_label(cfg: config.Config, store: Store) -> dict[str, object]:
    pull(cfg, FakeSearch(), store, NOW)
    group.assign_stories(store, FakeModels(), cfg.group_batch_size, NOW - LOOKBACK)
    verdicts = group.decide(store, cfg.confirm, NOW)
    titles = {s.id: s.title for s in store.stories()}
    return {titles[sid]: v for sid, v in verdicts.items()}


def test_single_source_rumour_is_rejected_with_its_reason(cfg, store) -> None:
    rumour = verdicts_by_label(cfg, store)["rumour"]
    assert rumour == Rejected("rejected: 1 publisher, no primary source", ("viralpaisa.xyz",))


def test_wire_story_reposted_by_five_outlets_counts_as_one_publisher(cfg, store) -> None:
    fed = verdicts_by_label(cfg, store)["fed_pause"]
    assert fed == Rejected(
        "rejected: 2 publishers in 24h (need 3), no primary source", ("Reuters", "cnbc.com")
    )


def test_primary_source_confirms_alone(cfg, store) -> None:
    rbi = verdicts_by_label(cfg, store)["rbi_hike"]
    assert isinstance(rbi, Confirmed) and rbi.primary_source == "rbi.org.in"


def test_three_publishers_in_a_day_confirm_but_not_spread_over_two(cfg, store) -> None:
    verdicts = verdicts_by_label(cfg, store)
    assert verdicts["opec_cut"] == Confirmed(("Bloomberg", "ft.com", "wsj.com"), None)
    assert verdicts["tariff_slow"] == Rejected(
        "rejected: 2 publishers in 24h (need 3), no primary source",
        ("axios.com", "cnn.com", "politico.com"),
    )


def test_pull_skips_unusable_results_and_never_stores_an_article_twice(cfg, store) -> None:
    first = pull(cfg, FakeSearch(), store, NOW)
    second = pull(cfg, FakeSearch(), store, NOW)
    assert (first.new_articles, first.skipped) == (18, 2)
    assert second.new_articles == 0
    assert store.counts()["articles_total"] == 18


def test_grouping_twice_makes_no_second_call_and_no_new_story(cfg, store) -> None:
    models = FakeModels()
    pull(cfg, FakeSearch(), store, NOW)
    first = group.assign_stories(store, models, cfg.group_batch_size, NOW - LOOKBACK)
    second = group.assign_stories(store, models, cfg.group_batch_size, NOW - LOOKBACK)
    assert (first.new_stories, first.assigned) == (5, 18)
    assert (second.calls, second.new_stories) == (0, 0)
    assert models.group_calls == [18]


def test_a_late_article_joins_its_open_story(cfg, store) -> None:
    models = FakeModels()
    raws = FakeSearch().results
    late = dict(raws[0], url="https://viralpaisa.xyz/late", publishedDate="2026-10-25T01:00:00Z")
    models.labels[normalize_url(late["url"])] = "rumour"
    pull(cfg, FakeSearch(raws), store, NOW)
    group.assign_stories(store, models, cfg.group_batch_size, NOW - LOOKBACK)
    pull(cfg, FakeSearch([late]), store, NOW)
    second = group.assign_stories(store, models, cfg.group_batch_size, NOW - LOOKBACK)
    assert (second.new_stories, second.assigned) == (0, 1)
    assert store.counts()["stories_total"] == 5


def test_wire_markers_need_a_word_boundary() -> None:
    wires = {"PTI": ("(PTI)", "PTI -")}
    assert origin_of("x.com", "NEW DELHI (PTI) - The", wires) == "PTI"
    assert origin_of("x.com", "OPTIONS -  traders", wires) == "x.com"


def test_utm_and_fragment_are_dropped_from_the_key() -> None:
    assert normalize_url("HTTPS://Example.ORG/a?utm_source=x&id=2#top") == (
        "https://example.org/a?id=2"
    )


def test_a_subdomain_of_a_primary_domain_is_primary(cfg) -> None:
    at = NOW
    art = Article("https://m.rbi.org.in/x", "rbi.org.in", "rbi.org.in", "t", "", at, "q", at)
    strict = dataclasses.replace(cfg.confirm, primary_host_prefixes=())
    assert group.confirm([art], strict) == Confirmed(("rbi.org.in",), "rbi.org.in")


def test_a_later_batch_joins_a_story_with_a_stale_publish_date(cfg, store) -> None:
    stale = [{**r, "publishedDate": "2026-01-24T00:00:00Z"} for r in FakeSearch().results]
    pull(cfg, FakeSearch(stale), store, NOW)
    out = group.assign_stories(store, FakeModels(), 1, NOW - LOOKBACK)
    assert out.calls == store.counts()["articles_total"] > 1
    assert out.new_stories == len(set(story_labels().values()))
