"""The whole cycle on fixtures: idempotent, deadline-bounded, and honest in its report."""

from __future__ import annotations

import dataclasses
import time
from pathlib import Path

import httpx2
import pytest

from networth import config, net
from networth.engine import backtest
from networth.engine.model import EventType, Region, write_db
from networth.llm import Classified
from networth.watcher import log, prices, report, run
from networth.watcher.pull import ExaSearch
from tests.watcher_fakes import (
    EVENT_DAY,
    FAKE_ENV,
    NOW,
    FakeCloses,
    FakeModels,
    FakeSearch,
    NeverConnects,
)

DEADLINE_S = 0.5
AGE = log.Age(NOW, 7)
SLACK_S = 1.0


@pytest.fixture
def cfg() -> config.Config:
    return config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)


@pytest.fixture
def paths(tmp_path: Path, tiny_book) -> run.Paths:
    paths = run.Paths(tmp_path / "data")
    paths.data_dir.mkdir()
    write_db(paths.rates_db, backtest.build(*tiny_book))
    return paths


def test_running_twice_keeps_counts_and_asks_the_models_only_for_new_work(cfg, paths) -> None:
    models = FakeModels()
    first = run.run_cycle(cfg, paths, FakeSearch(), models, NOW, FakeCloses()).cycle.counts
    second = run.run_cycle(cfg, paths, FakeSearch(), models, NOW, FakeCloses()).cycle.counts
    assert (first["articles_total"], first["stories_total"]) == (18, 5)
    assert (second["articles_total"], second["stories_total"]) == (18, 5)
    assert models.group_calls == [18]
    assert sorted(models.classified) == ["opec_cut", "rbi_hike"]
    assert second["articles_new"] == second["stories_new"] == second["classified"] == 0


def test_cycle_counts_rejections_by_reason(cfg, paths) -> None:
    outcome = run.run_cycle(cfg, paths, FakeSearch(), FakeModels(), NOW, FakeCloses())
    assert outcome.rejected_by_reason == {
        "rejected: 1 publisher, no primary source": 1,
        "rejected: 2 publishers in 24h (need 3), no primary source": 2,
    }


def test_report_lists_confirmed_with_sources_and_rejected_with_reasons(cfg, paths) -> None:
    run.run_cycle(cfg, paths, FakeSearch(), FakeModels(), NOW, FakeCloses())
    text = "\n".join(report.render(paths, NOW - report.dt.timedelta(hours=48), AGE))
    assert "confirmed via primary source rbi.org.in" in text
    assert "rejected: 1 publisher, no primary source; publishers: viralpaisa.xyz" in text
    assert "news-first ^NSEBANK: hit rate" in text
    assert not any(word in text.lower().split() for word in ("buy", "sell"))


def test_missing_key_exits_2_naming_the_key_without_traceback(tmp_path, capsys) -> None:
    env = tmp_path / ".env"
    env.write_text("EXA_API_KEY=exa-test-not-real\n")
    code = run.main(["--once", "--env-file", str(env), "--data-dir", str(tmp_path)], environ={})
    err = capsys.readouterr().err
    assert code == 2
    assert "OPENAI_API_KEY is missing from .env" in err and "Traceback" not in err


def test_exa_search_that_never_connects_ends_at_the_deadline_and_is_logged(cfg, tmp_path):
    fast = dataclasses.replace(
        cfg, http=config.HttpConfig(DEADLINE_S, DEADLINE_S, DEADLINE_S, DEADLINE_S)
    )
    transport = NeverConnects()
    log = tmp_path / "llm_calls.jsonl"
    search = ExaSearch(fast, log, client=httpx2.Client(transport=transport))
    start = time.monotonic()
    with pytest.raises(net.CallFailed):
        search.search(fast.pull.queries[0], NOW)
    assert time.monotonic() - start < DEADLINE_S + SLACK_S
    transport.release.set()
    (record,) = net.read_records(log)
    assert (record.ok, record.role) == (False, "exa")
    assert "DeadlineExceeded" in record.error


def test_a_cycle_whose_calls_all_fail_still_finishes_and_records_errors(cfg, paths) -> None:
    fast = dataclasses.replace(
        cfg, http=config.HttpConfig(DEADLINE_S, DEADLINE_S, DEADLINE_S, DEADLINE_S)
    )
    transport = NeverConnects()
    search = ExaSearch(fast, paths.call_log, client=httpx2.Client(transport=transport))
    small = dataclasses.replace(
        fast, pull=dataclasses.replace(fast.pull, queries=fast.pull.queries[:2])
    )
    outcome = run.run_cycle(small, paths, search, FakeModels(), NOW, FakeCloses())
    transport.release.set()
    assert len(outcome.cycle.errors) == 2 and outcome.cycle.counts["articles_new"] == 0


def test_report_counts_match_the_cycle_even_for_stale_publish_dates(cfg, paths) -> None:
    stale = [{**r, "publishedDate": "2026-01-24T00:00:00Z"} for r in FakeSearch().results]
    counts = run.run_cycle(
        cfg, paths, FakeSearch(stale), FakeModels(), NOW, FakeCloses()
    ).cycle.counts
    text = "\n".join(report.render(paths, NOW - report.dt.timedelta(hours=48), AGE))
    assert f"CONFIRMED ({counts['confirmed']})" in text
    assert f"REJECTED ({counts['rejected']})" in text


def test_report_marks_an_event_older_than_the_cutoff_at_render_time(cfg, paths) -> None:
    day = report.dt.date(2026, 10, 7)
    answer = Classified(EventType.RBI_HIKE, "inflation", day, Region.IN, "repo rate raised")
    run.run_cycle(cfg, paths, FakeSearch(), FakeModels({"rbi_hike": answer}), NOW, FakeCloses())
    since = NOW - report.dt.timedelta(hours=48)
    text = "\n".join(report.render(paths, since, AGE))
    assert "old news: rbi_hike dated 2026-10-07, older than 7 days" in text
    on_the_day = log.Age(report.dt.datetime(2026, 10, 8, tzinfo=report.dt.UTC), 7)
    assert "old news" not in "\n".join(report.render(paths, since, on_the_day))


def test_report_prints_two_stories_of_one_event_under_one_heading(cfg, paths) -> None:
    hike = Classified(EventType.RBI_HIKE, "inflation", EVENT_DAY, Region.IN, "repo rate raised")
    models = FakeModels({"rbi_hike": hike, "opec_cut": hike})
    run.run_cycle(cfg, paths, FakeSearch(), models, NOW, FakeCloses())
    lines = report.render(paths, NOW - report.dt.timedelta(hours=48), AGE)
    heading = lines.index("  EVENT rbi_hike on 2026-10-24")
    assert [ln.strip().split("  [")[0] for ln in lines[heading + 1 : heading + 5 : 2]] == [
        "rbi_hike",
        "opec_cut",
    ]
    assert sum("EVENT" in ln for ln in lines) == 1
    assert sum("news-first ^NSEBANK" in ln for ln in lines) == 1


@pytest.mark.parametrize(
    ("answers", "line"),
    [
        (None, "Newest confirmed India story: rbi_hike (2026-10-24), rbi_hike"),
        ({}, "Newest confirmed India story: none in window"),
    ],
)
def test_report_names_the_newest_confirmed_india_story(cfg, paths, answers, line) -> None:
    run.run_cycle(cfg, paths, FakeSearch(), FakeModels(answers), NOW, FakeCloses())
    assert line in report.render(paths, NOW - report.dt.timedelta(hours=48), AGE)


def test_price_first_checks_every_watched_asset_on_fresh_closes(cfg, paths) -> None:
    closes = FakeCloses()
    counts = run.run_cycle(cfg, paths, FakeSearch(), FakeModels(), NOW, closes).cycle.counts
    watched = {w.asset for w in cfg.triggers.price_watch}
    benchmarks = {w.benchmark for w in cfg.triggers.price_watch if w.benchmark}
    assert set(closes.asked) == watched | benchmarks
    assert counts["price_assets_checked"] == counts["price_assets_total"] == len(watched)


def test_a_failed_price_refresh_is_one_error_line(cfg, paths) -> None:
    def down(assets):
        raise prices.PricesUnavailable("DeadlineExceeded: yfinance closes: no answer within 60s")

    outcome = run.run_cycle(cfg, paths, FakeSearch(), FakeModels(), NOW, down)
    assert outcome.cycle.errors == (
        "price-first skipped: DeadlineExceeded: yfinance closes: no answer within 60s",
    )
    assert outcome.cycle.counts["price_assets_checked"] == 0


def test_an_asset_missing_from_the_download_is_named(cfg, paths) -> None:
    def partial(assets):
        full = FakeCloses()(assets)
        kept = {a: s for a, s in full.closes.items() if a != "XLK"}
        return prices.RecentCloses(kept, {"XLK": "no closes in the download"})

    outcome = run.run_cycle(cfg, paths, FakeSearch(), FakeModels(), NOW, partial)
    assert "no closes for XLK: no closes in the download" in outcome.cycle.errors
    counts = outcome.cycle.counts
    assert counts["price_assets_checked"] == counts["price_assets_total"] - 1
