# Phase 2 report: the news watcher and the model layer

The watcher now pulls the last 48 hours of news from Exa, groups articles into stories with the `cheap` model, and decides confirmation in plain code. The `judge` model classifies each confirmed story once. A confirmed, classified story calls the Phase 1 engine, and the resulting `Insight` rows hold only `odds()` output. Every story, confirmed or rejected, is in the decision log with its publishers and its reason.

## How to reproduce every check

```bash
uv sync
make check                                         # ruff, format, 112 tests (5 skip without data/)
uv run python -m networth.watcher.run --once       # one live cycle: pull, group, confirm, classify, trigger, log
uv run python -m networth.watcher.report           # stories decided in the last 48 h
uv run python -m networth.watcher.report --today   # since midnight, India time
grep -rn "gpt-" networth/ --include='*.py'         # finds nothing
```

`run` writes `data/watcher.sqlite` and appends one line per paid call to `data/llm_calls.jsonl`. The engine's `data/base_rates.sqlite` must exist for insights. Without it the cycle still runs and records the missing file as an error.

## Role to model map

Model ids live only in `networth/config.toml`. Prices are per 1M tokens and come from each model's page on OpenAI's developer site, fetched 2026-10-25. The overview is https://developers.openai.com/api/docs/pricing .

| Role | Used for | Model | Input | Cached input | Output | OpenAI's intended use | Source |
|---|---|---|---|---|---|---|---|
| `cheap` | grouping articles into stories, every cycle | gpt-5.6-luna | $0.20 | $0.02 | $1.20 | "optimized for cost-sensitive workloads" | https://developers.openai.com/api/docs/models/gpt-5.6-luna |
| `judge` | classifying a confirmed story, once for all users | gpt-5.6-sol | $4.00 | $0.40 | $20.00 | "flagship model for complex professional work" | https://developers.openai.com/api/docs/models/gpt-5.6-sol |
| `writer` | later phases, unused here | gpt-5.6-terra | $2.00 | $0.20 | $12.00 | "balances intelligence and cost" | https://developers.openai.com/api/docs/models/gpt-5.6-terra |

Sol's price is promotional, "available at least through November 21, 2026" per the same page. The mapping follows `tech.html` section 05.1. The cheapest tier sorts articles, the strongest tier makes the once-per-event judgment, and the middle tier will write. Both live roles run at reasoning effort `low`.

## One real cycle

Run on 2026-10-25 at 01:06 IST (2026-10-24 19:36 UTC), from an empty `data/watcher.sqlite`. It finished in 133 seconds of wall time.

| Count | Value |
|---|---|
| Exa queries | 16 |
| Exa results | 147 |
| Articles stored | 146 (147 results; one URL repeated, inferred from 0 skipped) |
| Stories | 71 |
| Confirmed | 30 (19 via a primary source, 11 via 3 or more publishers) |
| Rejected | 41 |
| Rejected: 1 publisher, no primary source | 33 |
| Rejected: 2 publishers in 24h (need 3), no primary source | 8 |
| Classified by the judge | 30 of 30 confirmed |
| Classified as an engine type | 4 (2 tariff, 1 bank_stress, 1 pandemic) |
| Classified as none | 26, of which 4 are "old news" |
| Insights written | 10, every one equal to `odds(type, asset)` on the real file |
| Price-first jumps | 0 |
| Grouping repairs | 2 (4 articles the model left out became their own stories) |

The 26 "none" answers are mostly routine primary-source notices that confirm on their domain alone, such as RBI Treasury bill auctions, money supply releases and SEBI orders. The judge reads each one and says it is not a market event, so none of them reaches the engine.

**RBI.** The Oct 7 2026 repo hike is outside the 48-hour window, so it does not appear as a new event. Articles about it did arrive (Mint and Jagran Josh on the MPC minutes, Business Today on the hike). They grouped into "RBI October 2026 Monetary Policy Meeting", confirmed via 7 publishers, and the judge's answer was then rejected in code: "old news: rbi_hike dated 2026-10-07, before 2026-10-22". No Exa result came from rbi.org.in about the hike itself inside the window.

**Newest confirmed India story that reached the engine.** "RBI Restrictions on Puducherry Cooperative Urban Bank", confirmed via 5 publishers (dinamani.com, ibc24.in, kalkionline.com, magzter.com, newindianexpress.com). It was classified as `bank_stress / fund_freeze` and produced insights for ^NSEBANK (hit rate 0.667 against a 0.591 baseline over 9 episodes, 63 sessions) and XLF.

A second `--once` run 2.5 minutes later stored 7 new URLs that Exa had not returned the first time, and ignored the 140 it had already stored. It made 1 grouping call for those 7 and 1 judge call for the 1 new confirmed story. It wrote no duplicate article, story or insight.

## Cost

Every number below is summed from `data/llm_calls.jsonl`.

| | Calls | Input tokens | Output tokens | Cost |
|---|---|---|---|---|
| **First cycle, empty store** | | | | **$0.2871** |
| Exa | 16 | | | $0.1050 |
| cheap (luna) | 3 | 21,386 | 3,348 | $0.0083 |
| judge (sol) | 30 | 29,197 | 2,851 | $0.1738 |
| **Second cycle, 2.5 minutes later** | | | | **$0.1109** |
| Exa | 16 | | | $0.1050 |
| cheap (luna) | 1 | 2,676 | 376 | $0.0010 |
| judge (sol) | 1 | 1,014 | 43 | $0.0049 |

The brief's limit is $1 for one cycle. The first cycle, the expensive one, spent $0.29.

**Per day at 43 cycles (estimated, not measured).** Exa is fixed at 16 queries, so $0.105 × 43 = $4.52 a day. Model cost scales with new articles and new confirmed stories. The second cycle spent $0.006 on models for 7 new articles. A real 15-minute gap will bring more than that, so I estimate $0.3 to $1.0 a day for models (a guess from the two measured cycles). Together that is about $5 to $5.50 a day, or $150 to $165 a month. That is above `tech.html`'s $45 to $90 a month for Exa, because the brief asks for a query per event type in both India and the US. Halving the queries to 8 halves the Exa line. That is a config change.

A judge call costs $0.0058 on average (31 calls measured, the largest $0.011). The per-cycle cap is 40 calls, so the judge spends at most about $0.25 in one cycle at that mean.

## Done-when results

1. `make check` passes on a clean clone of `824926e` after `uv sync`: 112 passed, 5 skipped. The skips are the real-file tests, which need `data/`. In the shared working tree it is red only because of another builder's uncommitted files under `networth/bot/`.
2. With `OPENAI_API_KEY` removed, `run --once` prints `networth.watcher.run: OPENAI_API_KEY is missing from .env` and exits 2 with no traceback. `test_config_and_llm.py` also covers this.
3. `grep -rn "gpt-" networth/ --include='*.py'` finds nothing, and a test guards it. Pricing sources are in the table above and next to each price in `config.toml`.
4. The live cycle ran in 133 seconds for $0.2871. See "One real cycle".
5. `report` lists 31 confirmed stories with publishers or primary source, and 42 rejected stories with reasons, after the second run. The Oct 7 RBI hike is outside the window and shows as old news. The newest confirmed India story is named above.
6. `tests/test_watcher_confirm.py` rejects the planted single-source rumour (viralpaisa.xyz) with "rejected: 1 publisher, no primary source". A Reuters story reposted by 5 outlets counts as one publisher, "Reuters".
7. A confirmed `rbi_hike` fixture story produces Insights whose `odds_json` equals `odds("rbi_hike", asset)` for ^NSEBANK and ^NSEI. This is checked against a database built in the test and against the real `data/base_rates.sqlite`. On the live file, all 10 insights equal `odds(type, asset)`.
8. `tests/test_watcher_triggers.py`: a fixture jump at 1.1 times the 2.5-sigma threshold fires, and one at 0.9 times does not, both raw and in excess of a benchmark.
9. Exa and OpenAI calls over a transport that never connects each end within a 0.5-second deadline plus 1 second of slack, and each is logged with `ok=false` and `DeadlineExceeded`. A whole cycle where every call fails still finishes and records its errors.
10. Running the cycle twice on fixtures leaves 18 articles and 5 stories. The grouping model is called once, and the judge once per confirmed story. On live news a second run adds only URLs it has not seen.
11. This file.
12. `data/` and `.env` are gitignored. No key appears in any committed file or log line.

## Design, as built

- **Who decides what.** The cheap model only groups. Code alone decides confirmation: a primary-source domain (or its subdomain, or an `investor.`/`investors.`/`ir.` host), or 3 or more distinct origins within any 24-hour window. A wire byline such as "(Reuters)" or "(PTI)" sets the article's origin to the agency, so reposts count once. The judge names the type, cause and event date. Code then checks the type and cause against the pairs in `events.csv` and rejects an event dated before the window.
- **Shapes.** `Verdict = Confirmed | Rejected` and `Classification = Classified | NotAnEvent` are closed unions. `store.py` is the only module that knows the sqlite schema, the same way `engine/model.py` is for the engine.
- **Idempotency.** Articles are keyed by normalized URL. Story ids hash the first article's URL. Grouping sees only unassigned articles. The judge sees only stories with no classification. Insights are keyed by story, asset and trigger. Verdicts are recomputed from stored articles every cycle.
- **Network.** Every client binds an IPv4 local address, so a dead IPv6 route is never tried. Every Exa and OpenAI call runs under a wall-clock deadline (30 s and 120 s) in a daemon thread, and is logged whether it succeeds or not.

## Known gaps

- **Exa's dates are not publish dates.** Some results carry the crawl date or a date with no time. A May 2025 article arrived dated 2026-10-24. The judge's event-date check keeps such stories away from the engine, but the 24-hour publisher window can still count a stale article as a current publisher.
- **Primary domains confirm routine notices.** RBI auctions and SEBI orders confirm on their domain and take a judge call each, about $0.006 apiece. Every one was classified "none".
- **The same event can become two stories.** "U.S. Changes Tariffs on Canadian Goods" and "US Section 338 Tariff Target Changes" are the same event, split across grouping batches. Each wrote its own tariff insights, with identical numbers.
- **Assets are not filtered by region.** `assets_by_type` maps `bank_stress` to both XLF and ^NSEBANK, so an Indian cooperative bank's restrictions also produced an XLF insight. Stories carry no region field yet.
- **Reference class.** A small cooperative bank capping withdrawals counts as `bank_stress`, in the same class as the library's larger bank failures. An Ebola outbreak in Nigeria counts as `pandemic / ebola`, because the library has that cause. Both are the judge's calls and look generous.
- **Price first never fired live.** It reads the engine's cached closes, which end 2026-10-23, and the run does not refresh them. The test proves the rule; the live run found no jump past 2.5 sigma.
- **Wire detection is a text match.** A phrase such as "Reuters reported" in the first 300 characters folds an article into Reuters. That undercounts publishers, so it errs toward rejecting.
- **Publisher names** come from a small registrable-host heuristic, not the public suffix list.
- **Grouping is not perfect.** In the run above the model left 4 of 146 articles out of its answer. Each became its own story, so a story can be wrongly rejected for having 1 publisher. Each repair is listed in the cycle's errors.

## Deviations from the brief

- **`httpx2`, not `httpx`.** The installed `openai` SDK (3.37.0) requires an `httpx2.Client`. Exa uses the same client. It is declared in `pyproject.toml` because the code imports it, and `openai` already pulls it in.
- **Extra primary domains.** Beyond the brief's list: finmin.nic.in, indiabudget.gov.in, treasury.gov, ustr.gov, whitehouse.gov, who.int, and investor-relations hosts by prefix.
- **The judge returns an event date, and code rejects old events.** The brief does not ask for this. The first live run needed it. Without it, a recrawled May 2025 airstrike article and the Oct 7 RBI hike were both classified as new events.
- **Grouping is repaired, not discarded.** When the model's answer breaks a rule, the valid groups are kept and the bad entries fixed. Discarding the whole answer split 2 of 3 batches into single-article stories on the first live run, which produced 84 artificial "1 publisher" rejections.
- **Price jumps only count inside the lookback**, so an old jump does not fire every cycle.
- **News-first insights use the all-causes row** of `odds(type, asset)`. The story's cause is stored next to it. Cause rows are smaller and often weak.
- **Insights have no `user_id`.** They are shared. Filtering per user is a later phase.
- **The report** lists stories decided in the last 48 hours by default, with `--today` for since midnight India time, because a just-run cycle's stories may carry older publish dates.
- **Branch policy and the shared tree.** Commits go straight to `main`, as the brief says, which overrides `~/.claude/CLAUDE.md` for this phase. Other builders share this working tree. Each commit stages only Phase 2 paths by name and is gated on a clean clone, as the coordinator asked.
- **Process.** The owner asked for `pstack:poteto-mode`. I wrote the design, and a delegate wrote the first four commits. I reviewed them, ran the live cycles, and made the two fix commits after the live runs. I skipped poteto-mode's parallel design exploration, because the brief already fixes the file layout and the data shapes.
