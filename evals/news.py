"""The news judge on labelled real stories: the watcher's confirmation rule, then its judge,
then its freshness rule, scored against labels written before the run.

    raw = run(labels, cfg, models, env)     # paid: the judge and Jev on every row
    scores = score(labels, raw)             # offline: precision, recall, false confirms

Each row's articles go through pull.parse_result and group.confirm exactly as pulled articles
do. The judge runs on every row so its own accuracy is visible apart from the rule; the
production prediction uses its answer only for a confirmed story whose event is fresh on the
row's seen_on date (triggers.oldest_event). Jev gets one Choice over the same types.
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from evals import spend
from networth.chat import jev
from networth.config import Config, Query
from networth.engine.model import EventType, Region
from networth.llm import (
    AllowedCauses,
    ArticleBrief,
    Classified,
    Models,
    StoryForJudge,
    _classify_prompt,
)
from networth.watcher import classify, group, pull, triggers
from networth.watcher.store import Confirmed

LABELS: Final = Path(__file__).with_name("news") / "labels.jsonl"
NONE: Final = "none"
JEV_QUESTION: Final = (
    "Which market event does this news story report as having just happened? Pick a type "
    "only when the story reports the event itself, not commentary, a preview, an anniversary "
    "or a decision to hold."
)
# The meanings in evals/news/LABELLING.md, so Jev and the labels read the same definitions.
JEV_CRITERIA: Final[dict[str, str]] = {
    "oil_supply": "OPEC or a war changes crude oil supply",
    "fed_hike": "the US Federal Reserve raises its policy rate",
    "fed_cut": "the US Federal Reserve cuts its policy rate",
    "rbi_hike": "the Reserve Bank of India raises the repo rate",
    "rbi_cut": "the Reserve Bank of India cuts the repo rate",
    "union_budget": "India's Union Budget is presented",
    "inr_shock": "the Indian rupee falls sharply or hits a record low against the dollar",
    "military_conflict": "a war, strike or invasion starts or escalates",
    "tariff": "the US imposes or raises tariffs",
    "bank_stress": "a bank fails, has a run, is put under moratorium or is rescued",
    "pandemic": "the WHO declares a pandemic or a health emergency",
    "election": "a national election result is declared",
    NONE: "anything else: a hold, a preview, a rumour, an opinion, old news or other news",
}


def load_labels(path: Path = LABELS) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    valid = {t.value for t in EventType} | {NONE}
    bad = [r["id"] for r in rows if r["label"] not in valid]
    if bad or len({r["id"] for r in rows}) != len(rows):
        raise ValueError(f"bad labels or duplicate ids: {bad}")
    return rows


def articles(row: Mapping, cfg: Config) -> list:
    query = Query((), Region(row["region"]), row["headline"], (), "")
    pulled = dt.datetime.fromisoformat(row["seen_on"]).replace(tzinfo=dt.UTC)
    raws = [{"url": a["url"], "title": a["title"], "publishedDate": a["published"],
             "text": a["text"], "author": a.get("author", "")}
            for a in row["articles"]]  # fmt: skip
    return [a for r in raws if (a := pull.parse_result(r, query, pulled, cfg.confirm))]


def story(row: Mapping, arts: Sequence) -> StoryForJudge:
    briefs = tuple(ArticleBrief(a.url, a.publisher, a.title, a.summary,
                                a.published_at.date().isoformat()) for a in arts)  # fmt: skip
    return StoryForJudge(row["id"], row["headline"], briefs, dt.date.fromisoformat(row["seen_on"]))


def run_row(row: Mapping, cfg: Config, models: Models, env: Mapping[str, str],
            allowed: AllowedCauses, log_path: Path) -> dict:  # fmt: skip
    arts = articles(row, cfg)
    verdict = group.confirm(arts, cfg.confirm) if arts else None
    s = story(row, arts)
    spend.check()
    started = time.monotonic()
    answer = models.classify_story(s, allowed)
    judge_ms = round((time.monotonic() - started) * 1000)
    judge = ({"type": answer.type.value, "cause": answer.cause,
              "event_date": answer.event_date.isoformat(), "region": answer.region.value,
              "reason": answer.reason} if isinstance(answer, Classified)
             else {"type": NONE, "reason": answer.reason})  # fmt: skip
    pick = jev.choose(_classify_prompt(s, allowed), JEV_QUESTION, JEV_CRITERIA, env,
                      deadline_s=cfg.product.jev_deadline_s, log_path=log_path)  # fmt: skip
    return {"id": row["id"], "parsed_articles": len(arts),
            "confirmed": isinstance(verdict, Confirmed),
            "publishers": list(verdict.publishers) if verdict else [],
            "primary_source": verdict.primary_source if isinstance(verdict, Confirmed) else None,
            "reject_reason": getattr(verdict, "reason", None),
            "judge": judge, "judge_ms": judge_ms,
            "jev": {"name": pick.name, "confidence": pick.confidence,
                    "latency_ms": pick.latency_ms} if pick else None}  # fmt: skip


def run(labels: Sequence[Mapping], cfg: Config, models: Models, env: Mapping[str, str],
        log_path: Path = spend.CALL_LOG) -> dict:  # fmt: skip
    start = len(spend.rows(log_path))
    allowed = classify.allowed_causes()
    rows = [run_row(r, cfg, models, env, allowed, log_path) for r in labels]
    calls = spend.since(start, log_path)
    return {"run_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "event_max_age_days": cfg.event_max_age_days, "rows": rows,
            "cost_usd": round(sum(c["cost_usd"] or 0 for c in calls), 4),
            "calls": dict(Counter(f"{c['role']}:{c['call']}" for c in calls))}  # fmt: skip


def predicted(row: Mapping, out: Mapping, max_age_days: int) -> str:
    """The watcher's answer: a type only for a confirmed story whose event is still news."""
    judge = out["judge"]
    if not out["confirmed"] or judge["type"] == NONE:
        return NONE
    seen = dt.datetime.fromisoformat(row["seen_on"])
    oldest = triggers.oldest_event(seen, max_age_days)
    return judge["type"] if dt.date.fromisoformat(judge["event_date"]) >= oldest else NONE


def _prf(pairs: Sequence[tuple[str, str]]) -> dict:
    """(label, prediction) pairs -> precision and recall of 'confirmed event of type X'."""
    tp = sum(p == g != NONE for g, p in pairs)
    fp = sum(p != NONE and p != g for g, p in pairs)
    fn = sum(g != NONE and p != g for g, p in pairs)
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "recall": round(tp / (tp + fn), 4) if tp + fn else None}  # fmt: skip


def _accuracy(pairs: Sequence[tuple[str, str | None]]) -> dict:
    right = sum(g == p for g, p in pairs)
    return {"right": right, "n": len(pairs), "accuracy": round(right / len(pairs), 4)}


def score(labels: Sequence[Mapping], raw: Mapping) -> dict:
    outs = {o["id"]: o for o in raw["rows"]}
    age = raw["event_max_age_days"]
    pairs = [(r["label"], predicted(r, outs[r["id"]], age)) for r in labels]
    judge_types = [(r["label"], outs[r["id"]]["judge"]["type"]) for r in labels]
    jev_types = [(r["label"], (outs[r["id"]]["jev"] or {}).get("name")) for r in labels]
    false_confirms = [{"id": r["id"], "kind": r["kind"], "label": r["label"], "predicted": p,
                       "headline": r["headline"], "seen_on": r["seen_on"],
                       "publishers": outs[r["id"]]["publishers"],
                       "primary_source": outs[r["id"]]["primary_source"],
                       "judge": outs[r["id"]]["judge"], "note": r["note"]}
                      for r, (_, p) in zip(labels, pairs, strict=True)
                      if p != NONE and p != r["label"]]  # fmt: skip
    missed = [{"id": r["id"], "label": r["label"], "predicted": p, "headline": r["headline"],
               "confirmed": outs[r["id"]]["confirmed"],
               "reject_reason": outs[r["id"]]["reject_reason"], "judge": outs[r["id"]]["judge"]}
              for r, (_, p) in zip(labels, pairs, strict=True)
              if r["label"] != NONE and p != r["label"]]  # fmt: skip
    by_kind: dict[str, Counter] = {}
    for r, (_, p) in zip(labels, pairs, strict=True):
        c = by_kind.setdefault(r["kind"], Counter())
        c["rows"] += 1
        c["rule_confirmed"] += outs[r["id"]]["confirmed"]
        c["predicted_event"] += p != NONE
        c["right"] += p == r["label"]
    ms = sorted(o["judge_ms"] for o in raw["rows"])
    jev_ms = sorted(o["jev"]["latency_ms"] for o in raw["rows"] if o["jev"])
    judge_acc, jev_acc = _accuracy(judge_types), _accuracy(jev_types)
    return {"rows": len(labels), "positives": sum(r["label"] != NONE for r in labels),
            "regions": dict(Counter(r["region"] for r in labels)),
            "pipeline": _prf(pairs), "judge_alone": _prf(judge_types),
            "judge_type_accuracy": judge_acc, "jev_type_accuracy": jev_acc,
            "jev_answered": sum(o["jev"] is not None for o in raw["rows"]),
            "jev_at_least_as_accurate": jev_acc["accuracy"] >= judge_acc["accuracy"],
            "by_kind": {k: dict(v) for k, v in sorted(by_kind.items())},
            "false_confirms": false_confirms, "missed": missed,
            "cost_usd": raw["cost_usd"], "calls": raw["calls"],
            "judge_ms_median": statistics.median(ms), "judge_ms_p90": ms[int(0.9 * (len(ms) - 1))],
            "jev_ms_median": statistics.median(jev_ms) if jev_ms else None}  # fmt: skip
