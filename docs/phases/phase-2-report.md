# Phase 2 report: the news watcher and the model layer

The watcher now pulls the last 48 hours of news from Exa, groups articles into stories with the `cheap` model, and decides confirmation in plain code. The `judge` model classifies each confirmed story once. A confirmed, classified story calls the Phase 1 engine, and the resulting `Insight` rows hold only `odds()` output. Every story, confirmed or rejected, is in the decision log with its publishers and its reason.

## How to reproduce every check

```bash
uv sync
make check                                         # ruff, format, 250 tests (7 skip without data/)
uv run python -m networth.watcher.run --once       # one live cycle: pull, group, confirm, classify, trigger, log
uv run python -m networth.watcher.report           # stories decided in the last 48 h
uv run python -m networth.watcher.report --today   # since midnight, India time
grep -rn "gpt-" networth/ --include='*.py'         # finds nothing
```

`run` writes `data/watcher.sqlite` and appends one line per paid call to `data/llm_calls.jsonl`. It downloads the last 6 months of closes for every price-watch asset from yfinance each cycle, and writes none of them to disk. The engine's `data/base_rates.sqlite` must exist for insights. Without it the cycle still runs and records the missing file as an error. `report` loads the config for the old-news cutoff, so it needs the same keys as `run`.

## Role to model map

Model ids live only in `networth/config.toml`. Prices are per 1M tokens and come from each model's page on OpenAI's developer site, fetched 2026-10-25. The overview is https://developers.openai.com/api/docs/pricing .

| Role | Used for | Model | Input | Cached input | Output | OpenAI's intended use | Source |
|---|---|---|---|---|---|---|---|
| `cheap` | grouping articles into stories, every cycle | gpt-5.6-luna | $0.20 | $0.02 | $1.20 | "optimized for cost-sensitive workloads" | https://developers.openai.com/api/docs/models/gpt-5.6-luna |
| `judge` | classifying a confirmed story, once for all users | gpt-5.6-sol | $4.00 | $0.40 | $20.00 | "flagship model for complex professional work" | https://developers.openai.com/api/docs/models/gpt-5.6-sol |
| `writer` | later phases, unused here | gpt-5.6-terra | $2.00 | $0.20 | $12.00 | "balances intelligence and cost" | https://developers.openai.com/api/docs/models/gpt-5.6-terra |

Sol's price is promotional, "available at least through November 21, 2026" per the same page. The mapping follows `tech.html` section 05.1. The cheapest tier sorts articles, the strongest tier makes the once-per-event judgment, and the middle tier will write. Both live roles run at reasoning effort `low`.

## One real cycle

Run on 2026-10-25 at 01:45 IST (2026-10-24 20:15 UTC), after review round 2, from an empty `data/watcher.sqlite`. It finished in 144 seconds of wall time.

| Count | Value |
|---|---|
| Exa queries | 16 |
| Exa results | 147 |
| Articles stored | 146 (147 results; one URL repeated, inferred from 0 skipped) |
| Stories | 73 |
| Confirmed | 28 (18 via a primary source, 10 via 3 or more publishers) |
| Rejected | 45 |
| Rejected: 1 publisher, no primary source | 38 |
| Rejected: 2 publishers in 24h (need 3), no primary source | 4 |
| Rejected: 1 publisher in 24h (need 3), no primary source | 3 (2 or more publishers, but only 1 inside any 24 h) |
| Classified by the judge | 28 of 28 confirmed (13 India, 12 US, 3 global) |
| Classified as an engine type | 6 (rbi_hike, bank_stress, military_conflict, oil_supply, pandemic, tariff) |
| Of those, old news (event more than 7 days before the cycle) | 3 (rbi_hike 2026-10-09, military_conflict 2025-05-07, oil_supply 2026-03-16) |
| Classified as none | 22 |
| Insights written | 5, every one equal to `odds(type, asset)` on the real file |
| Price-first assets evaluated | 24 of 24, on closes through 2026-10-23 (Friday, the last session) |
| Price-first jumps | 0 |
| Grouping repairs | 1 (1 article the model left out became its own story) |

The 22 "none" answers are mostly routine primary-source notices that confirm on their domain alone, such as RBI Treasury bill auctions, Fed statistical releases and SEBI orders. The judge reads each one and says it is not a market event, so none reaches the engine.

The 5 insights are 3 events, each mapped only to assets in its own region. Pandemic (Ebola reaches Nigeria, 2026-10-20, global) maps to SPY and ^NSEI. Bank stress (RBI restricts Puducherry Co-operative Urban Bank, 2026-10-22, India) maps to ^NSEBANK only, no longer XLF. Tariff (US changes Section 338 tariffs on Canadian goods, 2026-10-23, US) maps to SPY and XLI, no longer ^NSEI.

**RBI.** The Oct 7 2026 repo hike is outside the 48-hour pull window, but articles about it arrived. They formed one story, "RBI raises repo rate to 5.50%", confirmed via 7 publishers (businesstoday.in, econotimes.com, jagranjosh.com, livemint.com, mukhyamantri.com, psuconnect.in, sanskritiias.com). The report shows it as `EVENT rbi_hike on 2026-10-09` with "old news: rbi_hike dated 2026-10-09, older than 7 days", so it wrote no insight. The judge dated it Oct 9, not Oct 7. Either date is old news. No Exa result came from rbi.org.in about the hike inside the window.

**Newest confirmed India story.** The report's first line reads "Newest confirmed India story: Renewed India-Pakistan military tensions and Operation Sindoor fallout (2026-10-24), military_conflict dated 2025-05-07, old news". The newest India story that reached the engine is the Puducherry bank restriction. It was confirmed via 5 publishers and classified `bank_stress / fund_freeze`. Its ^NSEBANK insight shows a hit rate of 0.667 against a 0.591 baseline over 9 episodes, 63 sessions.

A second `--once` run 4 minutes later stored the 5 URLs Exa had not returned the first time, and ignored the 142 it already held. It made 1 grouping call and no judge call, because the new story was rejected. It still held 5 insights, and the store has no duplicate URL.

## Cost

Every number below is summed from `data/llm_calls.jsonl`.

| | Calls | Input tokens | Output tokens | Cost |
|---|---|---|---|---|
| **First cycle, empty store** | | | | **$0.2885** |
| Exa | 16 | | | $0.1050 |
| cheap (luna) | 3 | 22,100 | 3,926 | $0.0091 |
| judge (sol) | 28 | 29,950 | 2,727 | $0.1743 |
| **Second cycle, 4 minutes later** | | | | **$0.1060** |
| Exa | 16 | | | $0.1050 |
| cheap (luna) | 1 | 2,773 | 331 | $0.0010 |

The yfinance download is free and not in the log. It took 0.45 s for 2 tickers in the delegate's smoke call. In the full cycle all 24 tickers (the benchmarks SPY and ^NSEI are watched assets too) came back inside the 60-second deadline.

The brief's limit is $1 for one cycle. The first cycle, the expensive one, spent $0.29.

**Per day at 43 cycles (estimated, not measured).** Exa is fixed at 16 queries, so $0.105 × 43 = $4.52 a day. Model cost scales with new articles and new confirmed stories. The second cycle spent $0.001 on models for 5 new articles. A real 15-minute gap will bring more than that, so I estimate $0.3 to $1.0 a day for models (a guess from the two measured cycles). Together that is about $5 to $5.50 a day, or $150 to $165 a month. That is above `tech.html`'s $45 to $90 a month for Exa, because the brief asks for a query per event type in both India and the US. Halving the queries to 8 halves the Exa line. That is a config change.

A judge call costs $0.0062 on average (28 calls in the cycle above, $0.1743 in total). The per-cycle cap is 40 calls, so the judge spends at most about $0.25 in one cycle at that mean.

## Done-when results

1. `make check` passes on a clean clone of `816b918` after `uv sync`: 250 passed, 7 skipped. That count includes the other phases' tests now on `main`. The skips are real-file tests that need `data/`. In the shared working tree it can be red from another builder's uncommitted files.
2. With `OPENAI_API_KEY` removed, `run --once` prints `networth.watcher.run: OPENAI_API_KEY is missing from .env` and exits 2 with no traceback. `test_config_and_llm.py` also covers this.
3. `grep -rn "gpt-" networth/ --include='*.py'` finds nothing, and a test guards it. Pricing sources are in the table above and next to each price in `config.toml`.
4. The live cycle ran in 144 seconds for $0.2885. See "One real cycle".
5. `report` lists 28 confirmed stories with publishers or primary source, and 46 rejected stories with reasons, after the second run. Confirmed stories that classify to the same type and event date print under one `EVENT` heading. The Oct 7 RBI hike is outside the window and shows as old news. The first line names the newest confirmed India story, with its event date and an old-news mark when it applies.
6. `tests/test_watcher_confirm.py` rejects the planted single-source rumour (viralpaisa.xyz) with "rejected: 1 publisher, no primary source". A Reuters story reposted by 5 outlets counts as one publisher, "Reuters".
7. A confirmed `rbi_hike` fixture story produces Insights whose `odds_json` equals `odds("rbi_hike", asset)` for ^NSEBANK and ^NSEI. This is checked against a database built in the test and against the real `data/base_rates.sqlite`. On the live file, all 5 insights equal `odds(type, asset)`.
8. `tests/test_watcher_triggers.py`: a move of 1.01 and -1.01 times the 2.5-sigma threshold fires, and 0.99 and -0.9 times do not, both raw and in excess of a benchmark. One test loads the shipped `config.toml` and drives `write_insights` with `cfg.triggers`, using a fixture whose jump is hardcoded at 1.01 times 2.5 sigma. Setting `price_multiple = 3.0` in the config turns that test red (1 failed, 24 passed), and 2.5 turns it green again. I ran both.
9. Exa and OpenAI calls over a transport that never connects each end within a 0.5-second deadline plus 1 second of slack, and each is logged with `ok=false` and `DeadlineExceeded`. A whole cycle where every call fails still finishes and records its errors.
10. Running the cycle twice on fixtures leaves 18 articles and 5 stories. The grouping model is called once, and the judge once per confirmed story. On live news a second run adds only URLs it has not seen, and judges only new confirmed stories.
11. This file.
12. `data/` and `.env` are gitignored. No key appears in any committed file or log line.

## Design, as built

- **Who decides what.** The cheap model only groups. Code alone decides confirmation: a primary-source domain (or its subdomain, or an `investor.`/`investors.`/`ir.` host), or 3 or more distinct origins within any 24-hour window. A wire byline such as "(Reuters)" or "(PTI)" sets the article's origin to the agency, so reposts count once. The judge names the type, cause, event date and region (in, us or global). Code checks the type and cause against the pairs in `events.csv`. The judge's answer is cached as a fact. Whether its event is old news is decided again on every cycle, against `classify.event_max_age_days = 7`. Stories routinely arrive 1 to 3 days after the event, because Exa's dates lag and regional outlets report late. A user who invests monthly still needs an event from the past week. 7 days is also well inside the engine's 21-session horizon, so the base rate still describes the period ahead. News-first assets are filtered by the story's region through the engine's `market_of`, and a global story keeps all of them.
- **Shapes.** `Verdict = Confirmed | Rejected` and `Classification = Classified | NotAnEvent` are closed unions. `store.py` is the only module that knows the sqlite schema, the same way `engine/model.py` is for the engine.
- **Idempotency.** Articles are keyed by normalized URL. Story ids hash the first article's URL. Grouping sees only unassigned articles. The judge sees only stories with no classification. Insights are keyed by event (type and event date), asset and trigger, so two stories of one event write one set. Grouping offers the model every story with an article pulled inside the lookback, so a later batch can join a story an earlier batch created. Verdicts are recomputed from stored articles every cycle.
- **Network.** Every client binds an IPv4 local address, so a dead IPv6 route is never tried. Every Exa and OpenAI call runs under a wall-clock deadline (30 s and 120 s) in a daemon thread, and is logged whether it succeeds or not. The yfinance download runs over a curl session forced to IPv4, under a 60-second deadline. If it fails, the cycle records one "price-first skipped" error.

## Known gaps

- **Exa's dates are not publish dates.** Some results carry the crawl date or a date with no time. A May 2025 article arrived dated 2026-10-24. The judge's event-date check keeps such stories away from the engine, but the 24-hour publisher window can still count a stale article as a current publisher.
- **Primary domains confirm routine notices.** RBI auctions and SEBI orders confirm on their domain and take a judge call each, about $0.006 apiece. Every one was classified "none".
- **Rejected stories are not merged with their event.** Only confirmed stories are judged, so only they can be grouped by type and event date. In the cycle above "Changes to U.S. Section 338 tariff targets" (2 publishers) is rejected, while the same event is confirmed under `EVENT tariff on 2026-10-23`. The report shows both. Merging needs a second grouping pass over story titles, which this round did not add.
- **The judge's dates are approximate.** It dated the Oct 7 RBI hike Oct 9. A date that is a few days off can move an event across the 7-day line.
- **Reference class.** A small cooperative bank capping withdrawals counts as `bank_stress`, in the same class as the library's larger bank failures. An Ebola outbreak in Nigeria counts as `pandemic / ebola`, because the library has that cause. Both are the judge's calls and look generous.
- **Price first has not fired live.** It now evaluates every watched asset on fresh closes (24 of 24 in the cycle above), but no move passed 2.5 sigma on Oct 23. The tests prove the rule.
- **Wire detection is a text match.** A phrase such as "Reuters reported" in the first 300 characters folds an article into Reuters. That undercounts publishers, so it errs toward rejecting.
- **Publisher names** come from a small registrable-host heuristic, not the public suffix list.
- **Grouping is not perfect.** In the run above the model left 1 of 146 articles out of its answer. Each became its own story, so a story can be wrongly rejected for having 1 publisher. Each repair is listed in the cycle's errors.

## Deviations from the brief

- **`httpx2`, not `httpx`.** The installed `openai` SDK (3.37.0) requires an `httpx2.Client`. Exa uses the same client. It is declared in `pyproject.toml` because the code imports it, and `openai` already pulls it in.
- **Extra primary domains.** Beyond the brief's list: finmin.nic.in, indiabudget.gov.in, treasury.gov, ustr.gov, whitehouse.gov, who.int, and investor-relations hosts by prefix.
- **The judge returns an event date and a region, and code decides old news each cycle.** The brief does not ask for this. The first live run needed it. Without it, a recrawled May 2025 airstrike article and the Oct 7 RBI hike were both classified as new events. Round 1 compared the date with the start of the 48-hour window and cached the verdict, which dropped a story reported a day late for good. Round 2 caches only the judge's facts and applies a 7-day cutoff on every cycle.
- **The store migrates itself.** Opening a `watcher.sqlite` from before round 2 adds the new columns, clears every earlier classification (they lack a region and an event date) and deletes the insights, which are rebuilt the next cycle. The next cycle then judges those stories once more, about $0.006 each.
- **Price-first downloads its own closes.** It reads nothing from the engine's `data/prices` cache, and it writes nothing there. A price jump is explained only by a story whose region-filtered assets include that asset.
- **Grouping is repaired, not discarded.** When the model's answer breaks a rule, the valid groups are kept and the bad entries fixed. Discarding the whole answer split 2 of 3 batches into single-article stories on the first live run, which produced 84 artificial "1 publisher" rejections.
- **Price jumps only count inside the lookback**, so an old jump does not fire every cycle.
- **News-first insights use the all-causes row** of `odds(type, asset)`. The story's cause is stored next to it. Cause rows are smaller and often weak.
- **Insights have no `user_id`.** They are shared. Filtering per user is a later phase.
- **The report** lists stories decided in the last 48 hours by default, with `--today` for since midnight India time, because a just-run cycle's stories may carry older publish dates.
- **Branch policy and the shared tree.** Commits go straight to `main`, as the brief says, which overrides `~/.claude/CLAUDE.md` for this phase. Other builders share this working tree. Each commit stages only Phase 2 paths by name and is gated on a clean clone, as the coordinator asked.
- **Process.** The owner asked for `pstack:poteto-mode`. I wrote the design, and a delegate wrote the first four commits. I reviewed them, ran the live cycles, and made the two fix commits after the live runs. For review round 2 I wrote a design, a fresh delegate wrote the three fix commits, and I reviewed them, ran the live cycles and fixed the India line. I skipped poteto-mode's parallel design exploration, because the brief already fixes the file layout and the data shapes.
- **Commits in other commits.** Round 1's report and a config comment landed inside another session's commit, 98d6551, because that session committed while my files were staged. Round 2 commits use `git commit -- <paths>`.
