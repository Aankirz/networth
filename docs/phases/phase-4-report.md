# Phase 4 report: the web pages

The web pages are server-rendered from the engine. A judge can open `/why/rbi_hike/^NSEBANK` on a phone and see the count, the normal-period rate and all 22 past RBI hikes, each with its date, its RBI press release and its return. Each page is a FastAPI route in `networth/web/routes.py`. It calls `odds()`, `compare()` or `position_range()` and passes that JSON to a pure function in `views.py`, which turns it into words. The Jinja2 templates only print what they receive.

## How to reproduce every check

```bash
uv sync
make check                                  # ruff, format, all tests (48 in tests/test_web.py)
uv run python -m networth.web               # serves on 127.0.0.1:8090
uv run pytest -q tests/test_web.py          # the web tests alone, real-DB ones included when data/ exists
```

The browser checks below ran against `python -m networth.web` on the real `data/base_rates.sqlite`. They used Playwright with Chromium 1248, Lighthouse 12.6.0 with Chrome, and axe-core 4.10.3.

## Routes

| Route | Reads | What it shows |
|---|---|---|
| `/` | `compare()` | The tagline and a real scoreboard sample: RBI hikes, Indian banks next to Indian IT. A Telegram button to t.me/networth_professor_bot, and "Free. No account. Research, not advice." |
| `/why/{type}/{asset}` | `odds()` | The plain-word headline. The odds words and the lean. The weak-signal label when it applies. The horizon, and why day 0 is left out. Every episode with its date, headline, cause, source links, return, excess return, day-0 move and Beat or Lagged in words. The other eras with their overlap, the vault note, "What would change this view", and a share button next to the URL. |
| `/what-if/{type}/{asset}?amount=&currency=` | `position_range()`, `odds()` | p10, median and p90 in rupees (Indian grouping) or dollars. A strip with one dot per past episode, the p10 to p90 band and the median. The normal-month rate. It is labelled "History, not a forecast." |
| `/scoreboard/{type}` | `compare()` | Indian then US sector groups, in a fixed order with no ranks. Green, grey or red by the gap from baseline, with the lean also in words. Each row links to its Why card. |
| `/track-record` | `track_record` table if it exists | Rows rendered column by column. Otherwise "We start counting from our first message." |
| `/stats` | sqlite `COUNT`s | Events (287), episodes (255), base rates (3,020), distinct source links, event types, assets and the build date. No personal data. |
| `/static/networth.css` | file | The single stylesheet. It is served by a route because an `APIRouter` cannot mount `StaticFiles`. |
| unknown type, asset or row | | A friendly 404 page that links to every scoreboard. Bad amount or currency gets a friendly 400. |

`networth/web/__main__.py` serves the router alone on port 8090. Phase 3A mounts `networth.web.routes:router`. The database path is the `rates_db()` dependency, so tests override it.

## How numbers get from the engine to the page

1. A route calls the engine with the database path from `rates_db()`.
2. A function in `views.py` takes the engine's dict and builds strings. For example, `n_hits` and `n_episodes` go straight into "beat the Nifty 50 in 14 of 22". `baseline` is formatted as a percent. `p10`, `median` and `p90` are formatted as money by `fmt.money`, which uses Indian grouping and a U+2212 minus.
3. Word choices come from tables in `names.py`. Those are the plain names for 12 event types and 35 assets, the benchmark words, the odds-word scale from product.html section 06, and `LEAN_GAP = 0.10` for green, grey or red.
4. The only arithmetic outside the engine is the what-if strip's geometry: amount × each episode's raw return, which places a dot. Nothing it produces is printed as a number. A dot's tooltip shows the engine's own raw return.

`tests/test_web.py` builds a fixture sqlite through the real `backtest.build`. It then checks that every count, percent, money value, episode date and source URL on each page equals what `odds()`, `compare()` or `position_range()` returns for that fixture. A second set runs on the real file when it exists. It finds 14 of 22 on `/why/rbi_hike/^NSEBANK` and −$258, −$1 and +$211 on the JETS what-if. It also checks `/why` for every type × every asset (12 × 35) for banned words.

## Done-when results

1. **`make check`.** It passes from a clean clone after `uv sync`. The clean-clone run is recorded in the commit message.
2. **Six URLs return 200.** `/`, `/why/rbi_hike/^NSEBANK`, `/what-if/oil_supply/JETS?amount=2000&currency=USD`, `/scoreboard/rbi_hike`, `/track-record` and `/stats` all return 200 from the real database. `/why/nope/X` returns 404 and `amount=-5` returns 400.
3. **The RBI hikes page.** `/why/rbi_hike/^NSEBANK` reads "Indian banks (Nifty Bank) beat the Nifty 50 in 14 of 22 past RBI rate hikes. In a normal month, 56%." It lists 22 episodes, and its 22 distinct source links (rbi.org.in press releases) all returned HTTP 200 on 2026-10-25.
4. **The JETS what-if.** `/what-if/oil_supply/JETS?amount=2000&currency=USD` shows −$258, −$1 and +$211. That equals `position_range(2000, "JETS", "oil_supply")`.
5. **Wording.** `test_no_banned_words_and_research_line_on_every_page` covers every page on the fixture. The real-DB test covers all 420 `/why` pages. Neither finds "buy", "sell", "guaranteed" or "sure shot", and every page carries "Research, not advice."
6. **Widths.** No page scrolls sideways at 320 px or 1440 px, in either theme. The check measured `scrollWidth − clientWidth` on every page. The screenshots are below.
7. **Accessibility.** Lighthouse gives `/why/rbi_hike/^NSEBANK` 100 for accessibility on both the mobile and desktop presets, with performance 99 and 100. axe-core (WCAG 2 A and AA) finds 0 violations, colour contrast included, on all 7 pages in light and in dark.
8. **This file.**
9. **Nothing secret.** No secret is committed. `data/` stays gitignored.

## Screenshots

There are 24 full-page shots in `docs/phases/phase-4-shots/`, named `<page>-<width>-<theme>.png`. That is 6 pages × 320 and 1440 px × light and dark. For example, `why-320-light.png` and `what-if-1440-dark.png`.

## Design

The pages are styled like a printed research note. They use paper and ink colours, Newsreader for headings and big figures, and Public Sans with tabular figures for everything else. Green, grey and red appear only for the lean, and the lean is always written in words too. Below 40rem the episode table turns into stacked rows, so a phone reads one past case at a time. The only JavaScript is a few lines behind the share button. The URL is printed next to it, so sharing works without JS.

## Known gaps

- **No normal-month band.** The what-if strip has none because the engine stores only the baseline hit rate, not a distribution of normal-month returns. The normal-month rate appears as a sentence instead.
- **Only Telegram on the landing page.** WhatsApp is not live yet, and STOP wording waits for the bot.
- **`/track-record` schema.** It renders whatever columns a `track_record` table has. The real schema arrives with Phase 3B.
- **`/stats` counts.** It shows engine counts only. Users, briefs sent and reply rate need Phase 3B's store.
- **Onset headlines only.** `odds()` returns each episode's first headline, so a later event in an episode never shows. A display-reword table in `names.py` turns "agrees to buy" into "agrees to take over" in case such a headline ever shows. It is not reachable today.
- **Fonts load from Google Fonts.** Offline, the page falls back to the system serif and sans.

## Deviations from the brief

- **Odds scale.** The product table has no words for 30% to 44%. The pages say "Less often than not" there. The product owner should confirm it or replace it.
- **Lean threshold.** `LEAN_GAP` is 10 points between the hit rate and the baseline. With it, 14 of 22 (64%) against 56% reads "No clear pattern", which is honest at that gap. The threshold is one constant if the owner wants it moved.
- **Scoreboard groups.** `compare()` takes 2 or 3 assets, so the scoreboard is a set of groups whose members start on the same date. That way the shared-episode counts match each asset's own Why card: Indian banks show 14 of 22 on both. Each group says how many episodes it shares.
- **Currency mismatch.** A what-if in a currency other than the asset's own scales the engine's numbers and adds one line saying exchange-rate moves are left out.
- **Dependency files.** Adding `jinja2` meant committing `pyproject.toml` and `uv.lock`. They also carry Phase 3A's uncommitted `fastapi` and `uvicorn` lines, which the router needs too.
- **Process.** I designed the data shape and the routes, one delegate wrote the code, and I reviewed it. I reran every check above myself and added the favicon fix that Lighthouse asked for.

PHASE 4 READY FOR REVIEW
