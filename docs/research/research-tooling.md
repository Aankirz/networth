# Reusable tooling for the 24h investment-agent build

Research date: 2026-10-24. Scope: what exists today that the headline → verify → classify → analogs → excess-return lookup → plain-English reply loop, plus the daily brief, can reuse.

How it was checked:
- **[V]** means I checked it on the primary page, the GitHub API, the PyPI JSON API, or by running it. Pages were read with `tinyfish fetch`, stats came from `gh api`, and the price and FRED checks were run in the scratchpad.
- **[U]** means unverified: the claim came only from search snippets or a third party.
- Star counts and push dates come from `gh api` today.

Prior design (/Users/ankitkiran/Desktop/investment-os/architecture.html) is an odds engine + LLM narrator + nightly autoresearch, with DuckDB/Parquet, FastAPI and Python 3.12/uv. It uses "only official, timestamped sources in v1, no news scraping." The headline-verification loop needs news search, so it changes that rule.

---

## 1. Claude Code skills, plugins and Agent SDK examples (finance)

### Local machine (checked)
- `~/.claude/skills`: **no finance, news or market skills installed** [V]. The only hits for those keywords were unrelated (`skill-stocktake`, `continuous-learning`).
- `~/.claude/plugins/cache`: **no finance plugin installed** [V]. `exa` 3.4.1 is installed (claude-plugins-official), and the Exa MCP is also attached to this session as a claude.ai connector.
- The cached marketplace listings show plugins that could be installed (names and descriptions read from local `marketplace.json`) [V]:
  - claude-plugins-official: `firecrawl`, `exa`, `bigdata-com`, `linq-alpha`, `vanguard-advisor-tools`, `blackrock-advisor-center-plugin`, `zocks-advisor`.
  - cursor-plugins: `robinhood`, `webull`, `etoro-trading`, `sp-global`.
  - Most of these front paid or account-bound data. Only `firecrawl` and `exa` matter for the 24h build.

### Anthropic: `anthropics/financial-services` [V]
- 40.7k stars, Apache-2.0, pushed 2026-09-21. It is a Cowork/Claude Code plugin marketplace (`claude plugin marketplace add anthropics/financial-services`) plus Managed Agent cookbooks.
- Agents: Pitch, Meeting Prep, **Market Researcher**, **Earnings Reviewer**, Model Builder, Valuation Reviewer, GL Reconciler, Month-End Closer, Statement Auditor and KYC Screener.
- `equity-research` skills: `catalyst-calendar`, `earnings-analysis`, `earnings-preview`, `idea-generation`, `initiating-coverage`, `model-update`, **`morning-note`**, **`sector-overview`** and `thesis-tracker`.
- Connectors (`financial-analysis/.mcp.json`) are **all paid or enterprise**: Daloopa, Morningstar, S&P/Kensho, FactSet, Moody's, MT Newswires, Aiera, LSEG, PitchBook, Chronograph, Egnyte and Box. None are usable for free in 24h.
- The raw `.mcp.json` I fetched is malformed (a missing comma and brace near `box`). Copy it carefully if you use it.
- **What you can lift:** the `morning-note` SKILL.md structure (overnight developments → market context → key events today) is a ready template for the daily brief. The README's "not investment advice / staged for human review" wording is a usable disclaimer pattern.

### Community
- **tradermonty/claude-trading-skills** [V]: 3.2k stars, MIT, pushed 2026-10-20, about 80 skills. The most relevant are:
  - `market-news-analyst`: collects news via WebSearch/WebFetch and ranks impact, including FOMC/ECB/BOJ and geopolitical effects on commodities.
  - `scenario-analyzer`: headline → 18-month 1st/2nd/3rd-order scenarios, with a reviewer agent.
  - `news-reaction-failure-analyzer`: a drift-significance test on post-news price series.
  - `macro-regime-detector`, `sector-analyst`, `economic-calendar-fetcher` (needs an FMP key) and `weekly-performance-digest`.
  - Best source to crib classification prompts and a "regime" feature from.
- **quant-sentiment-ai/claude-equity-research** [V]: 744 stars, MIT, active. Single-stock buy/sell research; less relevant to event analogs.
- Directories such as mdskills.ai, agensi.io and awesomeskill.ai list more finance skills [U]. Quality varies and none were checked.

### Agent SDK
- **anthropics/claude-agent-sdk-demos** [V]: 2.8k stars, pushed 2026-08-27, no license file. It has general demos and **no finance-specific demo found** [U: I listed only the repo, not every demo].
- Anthropic's "Agents for financial services" post (anthropic.com/news/finance-agents, May 2026) describes the plugin repo above [V via search snippet].

---

## 2. MCP servers and APIs for market data and news

| Source | MCP | Free tier (primary page) | Historical depth | Licensing caveat |
|---|---|---|---|---|
| **Yahoo via yfinance** | Community: `Alex2Yang97/yahoo-finance-mcp` (362★, MIT), `narumiruna/yfinance-mcp` (204★, MIT) [V] | No key and no published limit. It is an unofficial scraper of Yahoo endpoints. | **Ran it** [V]: SPY 1993-01-29, XLK/XLE/XLF/XLV/XLI/XLY/XLP/XLU/XLB 1998-12-22, QQQ 1999-03-10, TLT 2002-07-30, GLD 2004-11-18, XLRE 2015-10-08, XLC 2018-06-19, BTC-USD 2014-09-17, ^GSPC 1927, ^SP500TR 1988-01-04 (yfinance 1.7.0) | Unofficial; Yahoo terms are personal use. It can break without notice (the TradingAgents v0.6.0 notes say "Yahoo's news feed is down" [V]). Show derived stats only and do not redistribute raw prices. |
| **Alpha Vantage** | Official, hosted at mcp.alphavantage.co; listed as an "Anthropic-Verified Connector" in Claude's directory [V]. Repo `alphavantage/alpha_vantage_mcp` (221★, MIT) [V]. | **25 requests/day** for most datasets. "Unlimited" for verified open-source or educational projects. Realtime and 15-min delayed US data is premium-only. [V] | 20+ years daily [U] | Licensed (NASDAQ-licensed vendor) [V]. 25/day is too few for a backfill but fine for a few live calls. |
| **Massive (formerly Polygon)** | Official `massive-com/mcp_massive` (398★, MIT, three tools: search/call/query) plus hosted `https://mcp.massive.com` [V] | Stocks Basic $0: **5 calls/min, 2 years history, EOD** [V]. $29 = 5y, $79 = 10y, $199 = 20y+ (individual use). | Free = 2y, **not enough for 1998** | Clean licensing on paid plans. |
| **Financial Datasets** | `financial-datasets/mcp-server` (2.3k★, MIT, **last push 2025-06-05**, stale) [V] plus official connectors [V] | No free tier. $20 one-time for 1,000 requests, $200/mo Personal [V]. | L1 prices 1y ($20) or 3y+ (Personal). Core data (financials, news, filings) 30y+. [V] | Personal license; redistribution only on the $2k/mo plan. |
| **Finnhub** | Official hosted `https://mcp.finnhub.io/mcp`, OAuth, 70 tools [V]. In Claude, "custom connectors … available on paid plans" [V]. | **60 calls/min**, personal use. Company news: 1 year plus real-time. Earnings calendar: 1 month. [V] | No free OHLC history (the 30+ years of OHLC is on the $3,500/mo plan) [V] | Personal use only on free [V]. |
| **Tiingo** | No official MCP found [U] | Free "Starter": **30+ years EOD**, 50 req/hour, 1,000 req/day, 500 unique symbols/month, 1 GB/month. News: 3 months queryable. [V] | 30+ years, covering 60,764 ETFs and mutual funds [V] | "Internal Use Only" [V] |
| **FRED** | Community `stefanoamorelli/fred-mcp-server` (127★, **AGPL-3.0**) [V]; `cfdude/mcp-fred` and `shanehull/fred-mcp` [U] | Free key | **Checked by CSV download** [V]: DFEDTAR 1982-09-27…2008-12-15, DFEDTARU 2008-12-16→, DCOILWTICO 1986→, DCOILBRENTEU 1987→, VIXCLS 1990→, DGS10 1962→, **CBBTCUSD 2014-12-01→**. SP500 covers only the last 10 years (2016-10-24→). | Terms: some series are third-party copyrighted (their notes say "Copyright"); FRED may limit use without notice [V]. |
| **SEC EDGAR** | `stefanoamorelli/sec-edgar-mcp` (374★, **AGPL-3.0**); `dgunning/edgartools` (2.8k★, MIT, has an MCP, PyPI 5.62.1 on 2026-10-23) [V] | Free. **Max 10 requests/sec**; you must declare a `User-Agent` with a contact email; data.sec.gov offers JSON APIs [V]. | 1994/95→ [V] | Public data |
| **OpenBB** | `openbb-mcp-server` 2.0.1 (PyPI, Apache-2.0, 2026-09-28) serves the OpenBB Platform routes as MCP tools [V] | Free; uses provider keys (yfinance, FRED, SEC and others) [U on the exact provider list] | Depends on the provider | `OpenBB-finance/OpenBB` now **redirects to `openbq-org/OpenBB`** on GitHub (74.6k★, licence shows NOASSERTION) [V, observed]. Check the licence before vendoring. |
| **GDELT** | Community `cyanheads/gdelt-mcp-server` (6★, Apache-2.0, "last 3 months", up to 250 articles) [V/U]. **GDELT Cloud** hosted MCP at `https://mcp.gdeltcloud.com/mcp`, OAuth or API key [V]. Its relationship to the GDELT Project and its pricing are [U]. | DOC 2.0 API: free, no key | DOC API search from 2017-01-01; non-timeline modes return only the latest 3 months of the window (2018 blog) [V]. **1.0 Event DB from 1979** (monthly/yearly files to Mar 2013, daily after) plus BigQuery [V]. | Open |
| **NewsAPI.org** | none needed | Developer $0: **100 req/day, 24-hour delay, 1-month archive, dev/test only** [V] | 1 month free; 5 years on $449/mo | Free tier is useless for live verification and not allowed in production [V] |
| **Exa** | `exa-labs/exa-mcp-server` (5.2k★, MIT) [V]; installed locally as a plugin | **$10 free credits/month plus a $10 onboarding bonus**, no card, 10 QPS [V]. Search costs about **$7 per 1k requests** (up to 10 results) [V: exa.ai/docs pricing snippet and blog]. | Web index; supports `startPublishedDate`/`endPublishedDate`, `category: "news"` and `includeDomains` [V: API reference] | Commercial API |
| **TinyFish** | CLI/SDK/MCP [V] | **Search free: 30 req/min, 500/hour. Fetch free: 150 URLs/min, 1,000/day.** Agent costs $0.016/step. [V] I hit the 30/min limit myself during this research. | Live web | Date filtering on search [U] |

---

## 3. Open-source investing agent frameworks and event-study libraries

| Project | Stars / activity [V] | Licence | What is actually liftable in 24h |
|---|---|---|---|
| **TauricResearch/TradingAgents** | 113.5k★, pushed 2026-10-16; v0.6.0 (Oct 2026) | Apache-2.0 | LangGraph multi-agent "trading firm" (analysts → researchers → trader → risk). **Too heavy to adopt.** Worth lifting: its **data-vendor layer with look-ahead filtering** ("backtests that see only data published by each analysis date", v0.5.2), FRED and Polymarket vendors, and the News/Sentiment analyst prompts. Research-only disclaimer. |
| **virattt/ai-hedge-fund** | 64.2k★, pushed today | MIT | Investor-persona agents. Not event-study oriented; skip. |
| **AI4Finance-Foundation/FinRobot** | 8.3k★, pushed 2026-09-28 | Apache-2.0 | Equity-research report agents. Little for the analog engine. |
| **AI4Finance-Foundation/FinGPT** | 21.5k★, pushed 2026-09-23 | MIT | Fine-tuned sentiment models and datasets. Not needed when Claude does the classification. |
| **AI4Finance-Foundation/FinRL** | 16.8k★ | MIT | RL trading; irrelevant. |
| **OpenBB** (openbq-org/OpenBB) | 74.6k★, pushed today; `openbb` 5.0.0 on PyPI | see licence note in §2 | One unified provider API with an MCP. Useful if you want a single data abstraction, but setup cost is real. Optional. |
| **ranaroussi/quantstats** | 7.7k★ | Apache-2.0 | Portfolio stats; not needed for N/hit-rate/median. |
| Event-study libs | `LemaireJean-Baptiste/eventstudy` 69★, last push 2023-12, **GPL-3.0**, PyPI 0.1a12 (2021). `EasyEventStudies` 2.0 (PyPI 2025-02). `event-study-toolkit` 1.0.0 (2023). `Darenar/easy-event-study` 3★. [V] | mixed | **All are low-activity.** Your metric (asset cumulative return minus SPY cumulative return over 5/21/63 trading days, from the next close after the event) is about 30 lines of pandas. Writing it yourself is faster and safer than adopting a GPL or alpha-quality library. Use eventstudytools.com's Python walkthrough only for the market-model variant. |

---

## 4. Firecrawl, and how it fits news verification

What Firecrawl is now [V, docs.firecrawl.dev and the pricing page, "effective September 4, 2026"]:
- **Endpoints:**
  - `/search`: web results plus full content, with `sources: ["web","news","images"]` and `categories` (research, developer, gov).
  - `/scrape`: markdown, HTML or JSON-schema output.
  - `/crawl`, `/map`, and `/interact` (click or type on a page).
  - `/monitor`: scheduled diffs and alerts.
  - **`/agent`**: autonomous data gathering with model `spark-2` and `max_credits`. It **replaces the legacy `/extract`**.
  - A "Alexandria" data-tool catalogue.
- **MCP:**
  - `firecrawl/firecrawl-mcp-server` (7.7k★, MIT, pushed today) has 27 tools.
  - A **hosted keyless endpoint at `https://mcp.firecrawl.dev/v2/mcp`** exposes `firecrawl_scrape`, `firecrawl_search` and `firecrawl_parse`.
  - A search-only endpoint, `/v2/mcp-search`, has 9 tools.
  - The core repo is 194.8k★ and **AGPL-3.0** if you self-host.
- **Pricing:**
  - **Free: 1,000 credits/month** (about 500 searches or 1,000 pages), 2 concurrent requests, about 10 requests/min per endpoint, no card.
  - Search costs 2 credits per 10 results; scrape costs 1 credit per page; JSON format adds 4 credits per page.
  - Agent: 5 free runs/day, then dynamic pricing.
  - Hobby $19/mo ($16 billed annually) for 5k credits; Standard $99/mo ($83 annually) for 100k.
  - Pages that return 403 or 404 still cost 1 credit.
  - A student program gives 10k credits.
- **Important caveat:** the `tbs` time filter **applies only to web results, not to `news` results** [V, search docs]. For "has this broken in the last 24h?", Firecrawl's news source cannot be date-bounded by the API.

Fit for the verify step (headline → is it real, how many independent outlets, since when):

| Option | Strength | Weakness | Cost |
|---|---|---|---|
| **Exa** | `category:"news"` plus `startPublishedDate` (for example, now minus 48h) plus `includeDomains`/`excludeDomains`. Returns `publishedDate`, so you can count distinct domains inside a time window. Has an MCP and is already installed locally. | Paid after the free credits (about $7 per 1k searches) | about $20 of free credit covers ~2–3k verifications |
| **TinyFish search/fetch** | Free and already your house tool; fetch handles anti-bot | No verified date filter; 30/min search cap (I hit it) | $0 |
| **GDELT DOC 2.0** | Free and keyless. Returns article lists across thousands of outlets with domain and seen-date, which makes it a good **independent-outlet counter** and lets you run a "timeline" volume spike check. | Noisy; English-centric ranking; latency of minutes; at most 250 records | $0 |
| **Firecrawl** | Best when the user texts a **URL**: scrape it to clean markdown, then the agent extracts claims and searches for corroboration | News results cannot be time-filtered; small free tier | 1,000 credits/mo free |
| NewsAPI free | none | 24h delay, dev-only | not viable |

---

## 5. Historical event datasets to seed the event library

| Event family | Source | Coverage | Status |
|---|---|---|---|
| **Fed rate decisions** | FRED `DFEDTAR` (1982-09-27→2008-12-15) plus `DFEDTARU`/`DFEDTARL` (2008-12-16→). Diff the series to get every target change date. | 1982→ | [V] CSV download works |
| | Wikipedia "History of Federal Open Market Committee actions" (61 KB page) | multi-decade table | [V] page exists |
| | **SF Fed U.S. Monetary Policy Event-Study Database (USMPD)**: FOMC statement, press-conference and minutes windows with high-frequency rate and stock changes, plus surprise measures. Updated 2026-09-17. | FOMC events with surprise sign; lets you split "hawkish surprise" from "dovish surprise" | [V] |
| **Bank failures** | **FDIC failed bank list CSV** at `https://www.fdic.gov/bank-failures/download-data.csv` (latest row: Nano Banc, 25-Sep-26) | Oct 2000→ | [V] downloaded |
| | Wikipedia "List of bank failures in the United States (2008–present)" | 2008→ | [V] page exists |
| **Geopolitical shocks / wars** | **Caldara–Iacoviello GPR index**: daily (1985→, updated Mondays, last 2026-10-19) and monthly (1900→, 44 country indexes) in Excel/Stata. Spikes above a threshold give dated shock events objectively. | 1900/1985→ | [V] |
| | LPL Research "Lessons From Past Conflicts" tables: about 21 dated geopolitical events with S&P drawdown and recovery, plus a wars-only subset. It is a chart, so expect manual transcription. Good **ground truth to sanity-check your numbers**. | WWII→2026 | [V] page; event count from a third party [U] |
| | ACLED: conflict events. The **Research tier has a 12-month delay**; registration (myACLED) is required. | 1997→ (varies by region) [U] | [V] delay |
| | GDELT 1.0/2.0 Event DB (1979→) and BigQuery | very noisy for "major event" selection | [V] |
| **Tariffs / trade war** | **PIIE "Trump's trade war timeline 2.0"** (updated 2026-10-16) and the US-China tariff chart | 2018→ (1.0 timeline PDF) and 2025→ | [V] via search, page dated |
| | Wikipedia "Tariffs in the second Trump administration" (175 KB) | 2025→ | [V] page exists |
| **OPEC decisions** | OPEC press releases (opec.org/press-releases.html) and Wikipedia "OPEC". **No clean structured dataset of decisions found.** | — | [U]: needs LLM extraction or a hand-built list of about 30 cuts and hikes |
| **Oil / VIX / rates shocks (rule-based)** | FRED Brent/WTI/VIX/DGS10 with threshold rules, as in the prior design | 1986–1990→ | [V] |
| **Crashes / bear markets** | Wikipedia "List of stock market crashes and bear markets" | long history | [V] page exists |
| **Corporate events (US)** | SEC EDGAR 8-K item codes via edgartools | 1994→ | [V] |

Practical seed for 24h: about 150–300 hand-curated, dated macro and geopolitical events. Build it with the LLM from the lists above, then let the user correct it.
- Each row: `date`, `type`, `subtype`, `region`, `source_url`.
- Example types: `fed_hike`, `fed_cut`, `fed_emergency_cut`, `bank_failure_large`, `war_start`, `opec_cut`, `tariff_announce`, `oil_spike_10pct`, `vix_spike`.

---

## 6. Free daily price history (sector ETFs, GLD, TLT, QQQ, BTC)

Verified by running `yfinance` 1.7.0 with `period="max"` and `auto_adjust=True` [V]:

| Ticker | First date | Note |
|---|---|---|
| SPY | 1993-01-29 | benchmark; use the adjusted close (total return) |
| ^SP500TR | 1988-01-04 | alternative total-return benchmark |
| XLB XLE XLF XLI XLK XLP XLU XLV XLY | **1998-12-22** | the 9 original SPDR sectors |
| QQQ | 1999-03-10 | |
| TLT | 2002-07-30 | |
| GLD | 2004-11-18 | before this, use FRED gold [U: the LBMA gold series on FRED may have been removed]. Otherwise skip. |
| XLRE | 2015-10-08 | |
| XLC | 2018-06-19 | |
| BTC-USD | 2014-09-17 | FRED `CBBTCUSD` from 2014-12-01 as a fallback [V]. **No free source checked here goes back before 2014.** |

Other sources:
- **Tiingo free**: 30+ years EOD and 1,000 req/day [V], enough to pull about 20 tickers once. Internal use only.
- **Stooq**: bulk free CSVs exist (stooq.com/db/h, updated 24 Oct 2026 [V]). However, `curl` on the per-ticker CSV endpoint now returns a **JavaScript proof-of-work bot wall** [V, observed]. Treat it as manual download only.
- **Massive free**: only 2 years [V]. **Alpha Vantage**: 25 calls/day [V]. Neither works for the backfill.

Implication: analog events before Dec 1998 can only be scored against SPY/^GSPC. Events before 2015/2018 have no XLRE/XLC, and events before 2014 have no BTC, so N differs by asset. Show N for each asset in the reply.

---

## Recommended stack for a 24h build

| Need | Pick | Fallback | Why |
|---|---|---|---|
| Daily price backfill (1998→) | **yfinance** → one-time pull to Parquet; precompute excess returns for 5/21/63 days versus SPY adjusted close | **Tiingo free API** (30y EOD, 1k req/day); FRED `CBBTCUSD` for BTC | Depth checked by running it; zero keys. Precomputing means Yahoo outages do not hit live replies. |
| Daily refresh for the brief | yfinance on a nightly cron on the Maritime VM | Tiingo; Alpha Vantage MCP (25/day) for a handful of quotes | |
| Macro series and rule-based events | **FRED CSV endpoint** (`fredgraph.csv?id=…`, no key needed for CSV) | FRED API with a key, or a community FRED MCP (note AGPL) | Fed targets, oil, VIX and 10Y are all checked. |
| Headline verification (search) | **Exa** search, `category:"news"`, `startPublishedDate` set to now minus 48h; count distinct domains; MCP already installed | **TinyFish search** (free) plus **GDELT DOC 2.0** `artlist`/`timelinevol` as a free independent-outlet counter | Only option checked here that has a primary-documented date filter on news; tiny cost. |
| Reading a pasted article URL | **TinyFish fetch** (free, 1k/day) | **Firecrawl scrape** (hosted keyless MCP, 1k credits/mo) | Both return clean text; Firecrawl is better on hard pages. |
| Event classification | Claude with a fixed taxonomy enum, crib prompts from tradermonty `market-news-analyst` / `scenario-analyzer` | none | No library needed. |
| Event library seed | Hand-curated CSV from FRED target diffs + SF Fed USMPD + FDIC CSV + GPR spikes + PIIE tariff timeline + Wikipedia lists | GDELT/ACLED later | All free and all checked except OPEC (hand-list it). |
| Event-study math | **Own about 30 lines of pandas** (next-close entry, cumulative excess versus SPY, N / hit rate / median, MIN_CASES gate) | `EasyEventStudies` for a market-model cross-check | Every library is stale or GPL. |
| Corporate events (if time) | **edgartools** (MIT, active) | `sec-edgar-mcp` (AGPL) | Remember the 10 req/s limit and the `User-Agent` header. |
| Daily brief format | Adapt `anthropics/financial-services` **`morning-note`** SKILL.md | tradermonty `weekly-performance-digest` | Ready structure plus a disclaimer pattern. |
| Agent framework | **Claude Agent SDK, written directly** (simple tool loop) | none | TradingAgents/FinRobot are too heavy for 24h; lift only TradingAgents' look-ahead-filter idea. |

Top risks:
1. **Yahoo licensing and stability.** Reply with derived statistics only, cache everything, and keep Tiingo ready.
2. **Small N** for niche event types. Keep the prior design's MIN_CASES gate and show N for each asset.
3. **Overlapping windows.** Clustered events, such as several Fed cuts in 2008, are not independent; dedupe within 21 trading days.
4. **Verification false positives** from syndicated copies (AP/Reuters reposts). Count distinct original publishers, not distinct URLs.

Not covered: the Keiki and Maritime platform APIs, which were out of scope for this pass.
