"""The eval scoring rules on hand-made statements: no data/, no network."""

from __future__ import annotations

import pytest

from evals import vault
from evals import walkforward as wf


def scored(hit_rate: float, baseline: float, hits: list[bool], n: int = 10) -> wf.Scored:
    weak = n < 8
    lean = wf.names.lean(hit_rate, baseline, weak).kind.value
    s = wf.Statement("rbi_hike", "^NSEBANK", "since_2007", "2016-01-01", n,
                     round(hit_rate * n), hit_rate, baseline, weak, lean)  # fmt: skip
    outs = tuple(wf.Outcome(f"e{i}", "2017-01-01", h) for i, h in enumerate(hits))
    return wf.Scored(s, outs)


def test_an_up_lean_holds_only_when_later_hits_beat_the_baseline() -> None:
    assert wf.held(scored(0.7, 0.5, [True, True, False])) is True
    assert wf.held(scored(0.7, 0.5, [True, False, False])) is False


def test_a_down_lean_holds_when_later_hits_fall_below_the_baseline() -> None:
    assert wf.held(scored(0.3, 0.5, [False, False, True])) is True


def test_weak_and_flat_statements_are_never_judged() -> None:
    assert wf.held(scored(0.9, 0.5, [True], n=5)) is None
    assert wf.held(scored(0.52, 0.5, [True])) is None
    assert wf.held(scored(0.7, 0.5, [])) is None


def test_calibration_buckets_the_likelier_side_and_counts_what_happened() -> None:
    rows = {r["bucket"]: r for r in wf.calibration([
        scored(0.65, 0.5, [True, True, False]),   # 65% hit: 60-70, hits happened 2 of 3
        scored(0.25, 0.5, [False, True]),         # 75% miss: 70%+, misses happened 1 of 2
        scored(0.9, 0.5, [True], n=5),            # weak: left out
    ])}  # fmt: skip
    assert (rows["60-70%"]["episodes"], rows["60-70%"]["happened"]) == (3, 2)
    assert (rows["70%+"]["episodes"], rows["70%+"]["happened"]) == (2, 1)
    assert rows["70%+"]["stated_mean"] == 0.75
    assert rows["50-60%"]["episodes"] == 0


def test_the_vault_refuses_a_second_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vault, "VAULT_JSON", tmp_path / "vault.json")
    (tmp_path / "vault.json").write_text("{}")
    with pytest.raises(SystemExit, match="scored once"):
        vault.main([])


def test_the_vault_refuses_after_an_unrecorded_crash(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vault, "VAULT_JSON", tmp_path / "vault.json")
    monkeypatch.setattr(vault, "STARTED", tmp_path / "vault.started")
    (tmp_path / "vault.started").write_text("x")
    with pytest.raises(SystemExit, match="after-crash"):
        vault.main([])
