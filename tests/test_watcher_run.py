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
from networth.watcher import log, report, run
from networth.watcher.pull import ExaSearch
from tests.watcher_fakes import FAKE_ENV, NOW, FakeModels, FakeSearch, NeverConnects

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
    first = run.run_cycle(cfg, paths, FakeSearch(), models, NOW).cycle.counts
    second = run.run_cycle(cfg, paths, FakeSearch(), models, NOW).cycle.counts
    assert (first["articles_total"], first["stories_total"]) == (18, 5)
    assert (second["articles_total"], second["stories_total"]) == (18, 5)
    assert models.group_calls == [18]
    assert sorted(models.classified) == ["opec_cut", "rbi_hike"]
    assert second["articles_new"] == second["stories_new"] == second["classified"] == 0


def test_cycle_counts_rejections_by_reason(cfg, paths) -> None:
    outcome = run.run_cycle(cfg, paths, FakeSearch(), FakeModels(), NOW)
    assert outcome.rejected_by_reason == {
        "rejected: 1 publisher, no primary source": 1,
        "rejected: 2 publishers in 24h (need 3), no primary source": 2,
    }


def test_report_lists_confirmed_with_sources_and_rejected_with_reasons(cfg, paths) -> None:
    run.run_cycle(cfg, paths, FakeSearch(), FakeModels(), NOW)
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
    fast = dataclasses.replace(cfg, http=config.HttpConfig(DEADLINE_S, DEADLINE_S, DEADLINE_S))
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
    fast = dataclasses.replace(cfg, http=config.HttpConfig(DEADLINE_S, DEADLINE_S, DEADLINE_S))
    transport = NeverConnects()
    search = ExaSearch(fast, paths.call_log, client=httpx2.Client(transport=transport))
    small = dataclasses.replace(
        fast, pull=dataclasses.replace(fast.pull, queries=fast.pull.queries[:2])
    )
    outcome = run.run_cycle(small, paths, search, FakeModels(), NOW)
    transport.release.set()
    assert len(outcome.cycle.errors) == 2 and outcome.cycle.counts["articles_new"] == 0


def test_report_counts_match_the_cycle_even_for_stale_publish_dates(cfg, paths) -> None:
    stale = [{**r, "publishedDate": "2026-01-24T00:00:00Z"} for r in FakeSearch().results]
    counts = run.run_cycle(cfg, paths, FakeSearch(stale), FakeModels(), NOW).cycle.counts
    text = "\n".join(report.render(paths, NOW - report.dt.timedelta(hours=48), AGE))
    assert f"CONFIRMED ({counts['confirmed']})" in text
    assert f"REJECTED ({counts['rejected']})" in text


def test_report_marks_an_event_older_than_the_cutoff_at_render_time(cfg, paths) -> None:
    day = report.dt.date(2026, 10, 7)
    answer = Classified(EventType.RBI_HIKE, "inflation", day, Region.IN, "repo rate raised")
    run.run_cycle(cfg, paths, FakeSearch(), FakeModels({"rbi_hike": answer}), NOW)
    since = NOW - report.dt.timedelta(hours=48)
    text = "\n".join(report.render(paths, since, AGE))
    assert "old news: rbi_hike dated 2026-10-07, older than 7 days" in text
    on_the_day = log.Age(report.dt.datetime(2026, 10, 8, tzinfo=report.dt.UTC), 7)
    assert "old news" not in "\n".join(report.render(paths, since, on_the_day))
