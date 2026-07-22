# Nighttrader — Design Document

Status: planning complete, implementation started (Phase 0 scaffold)
Purpose: hand-off brief for Claude Code. This file is the source of truth for architecture decisions made during design chat. Update it as the build evolves — don't let it drift out of sync with the code.

> Mirrored from the Notion page `NIGHTTRADER_DESIGN` (2026-07-22). If you edit one, sync the other.

---

## 1. Thesis

Standard CAPM logic holds: you can't systematically outrun the market without an information edge, and price history alone is only a proxy for the future. Nighttrader doesn't try to out-predict sub-second HFT — that race is unwinnable and isn't the goal.

The actual edge is **information diffusion lag**:
- 13F institutional filings disclose holdings 45 days after quarter-end
- Retirement/pension fund rebalancing follows committee and index cycles measured in weeks
- Sell-side rating changes propagate into retail flow over days
- Geopolitical shocks (erratic, unpredictable) are followed by *predictable* cascades through specific asset classes (a rate move cascades into financials/REITs, a conflict cascades into energy, a disaster cascades into insurance-linked securities)

The system's job: turn cheap, freely available, previously-hard-to-process information (macro data, filings, weather, event streams) into structured scenario reasoning that a non-specialist (economics background, not a financial analyst) can act on. Not a black box "buy" signal — a reasoning trail.

**Explicitly not the goal:** competing with HFT, giving personalized financial advice, promising outperformance. This is a personal research/decision-support tool, run with a small real budget for genuine skin in the game.

---

## 2. Asset Universe (locked in)

Four buckets, prioritized in this order for build purposes:

| # | Bucket | Examples | Risk profile | Why tracked |
|---|--------|----------|--------------|-------------|
| 1 | Rate-sensitive sector ETFs | XLF, XLU, XLRE (+ broad SPY/QQQ for baseline) | Moderate | Cleanest proving ground for the scenario engine — directly reacts to Fed/macro counterfactuals, cheap data, highly liquid |
| 2 | Insurance-linked securities | ILS (Brookmont Cat Bond ETF, NYSE), KRC (UCITS, Europe) | Moderate-high, low correlation to broader market | Returns driven by discrete trigger events, not economic cycles. See RT-3 for the honest version of this edge |
| 3 | Diversifiers | GLD (gold), BTC/ETH ETFs | Small allocation by design | Gold correlates with real rates (FRED-derived), crypto is sentiment/liquidity-driven (Trends-derived). No dedicated agent needed |
| 4 | Aggressive/growth sleeve | Thematic (semis, AI infra), leveraged sector ETFs | High | Deferred to post-v1 |

---

## 3. Agent Architecture

Fork target: **TradingAgents** (TauricResearch, Apache 2.0, LangGraph-based, native Claude support). Used as a pinned dependency, NOT vendored (RT-9). Chosen over `ai-hedge-fund` (less structured debate pattern) and Qlib (better as a backtesting backbone than an agent framework).

### Flow

```
[Shock Detector — GDELT]
  Monitors coded global events (CAMEO format, 15-min updates), filters the
  firehose down to things worth reasoning about. Auto-populates Scenario
  Input, or you inject one manually.
        ↓
[Scenario Input] ←── [Scenario Priors]
  A counterfactual: "Fed +0.1%", "Cat 4 landfall Tampa". Every scenario
  carries a market-implied probability where one exists: CME FedWatch,
  Polymarket/Kalshi. Scenarios with no tradeable prior get an explicit
  "prior: none, user-assumed" label. Must be threaded into every downstream
  agent's own tool calls, not just prepended once as a prompt note.
        ↓
[Parallel Analysts]
  Fundamentals      — earnings, balance sheets
  Technical         — Kronos price simulation as an UNCONDITIONAL baseline
                       (RT-1: scenario adjustment happens at the reasoning
                       layer, on top of the Kronos baseline, not inside it)
  Sentiment         — Google Trends + social signal
  News              — recent coverage, sell-side notes
  Institutional Lag — 13F deltas, fund flows not yet priced in
  Cat/Weather       — seasonal ILS spread cycles + post-event dislocation
                       (RT-3 reframe; NOT landfall prediction)
        ↓
[Bull/Bear Researchers] — debate analyst output under the scenario
        ↓
[Devil's Advocate] — finds the OPPOSITE historical case (RT-2)
        ↓
[Research Manager] — synthesizes, checks consistency against FRED backdrop
        ↓
[Risk Manager] — position sizing, correlation, volatility bounds
        ↓
[Portfolio Manager] — final ranked output + full reasoning trail
        ↓
[Guard (deterministic, no LLM)] — universe whitelist, size/turnover caps,
  no-short/no-margin, loss halt, live human-confirm (§11.4). The LLM
  proposes; guard.py disposes.
```

### Design principle

Every new agent (Institutional Lag, Cat/Weather, Shock Detector) is additive to the existing TradingAgents graph, not a rewrite. Most of the system is reused wiring; the differentiation is concentrated in ~3 new nodes plus the scenario-threading behavior.

---

## 4. Data Sources

| Source | Feeds | Access | Notes |
|--------|-------|--------|-------|
| FRED | Macro backdrop, rate scenarios | Free API | Use ALFRED vintages for any mechanical backtest (revision bias) |
| Kronos (NeoQuasar, HuggingFace) | Technical Analyst price simulation | Free, MIT, local inference | Candlestick foundation model, run locally (MPS on Apple Silicon) |
| Google Trends (`pytrends`) | Sentiment Analyst | Free, unofficial | Attention/sentiment proxy |
| GDELT (Cloud MCP or `gdeltPyR`) | Shock Detector | Free, 15-min updates | Firehose — relevance filter is real design work (§8.1) |
| 13F filings / fund flow data | Institutional Lag Analyst | Free (SEC EDGAR) to paid | Quarterly; 45-day disclosure lag is the whole point (see RT-11) |
| NOAA / National Hurricane Center | Cat/Weather Analyst | Free, public | Cone-of-uncertainty forecasts, seasonal outlooks |
| CME FedWatch | Scenario Priors | Free | Market-implied FOMC outcome probabilities |
| Polymarket / Kalshi | Scenario Priors | Free APIs | Traded probabilities on elections, geopolitics, hurricanes |
| Alpaca News API (Benzinga) | News Analyst | Free with Alpaca account | Real-time; zero extra vendor since Alpaca is the broker |
| Finnhub | News/Sentiment | Free tier, 60 calls/min | Most generous free tier |
| Alpha Vantage News & Sentiment | Sentiment Analyst | Free tier (25 req/day) | Official vendor MCP server |
| Marketaux | News Analyst (backup) | Free tier, 100 req/day | Entity-level sentiment |
| SEC EDGAR 8-K filings | Shock Detector / News | Free, structured | Material events hours before journalism; minimal injection surface |
| federalreserve.gov | Macro / Scenario | Free, primary | The actual text, not the write-up |
| Artemis.bm (RSS) | Cat/Weather Analyst | Free | ILS/cat-bond niche trade publication |
| FT Alphaville / Calculated Risk / Money Stuff (RSS) | Human learning layer | Free/partial | LOW weight; never scrape paywalled content |
| Anthropic financial-services skills | Various analysts | Claude Code plugin | `claude plugin install financial-analysis@claude-for-financial-services` |

**Sourcing principle:** prefer primary sources (filings, central bank text, NHC advisories, traded probabilities) over journalism. They arrive earlier, carry less narrative bias, and present a smaller prompt-injection surface (RT-5). Pre-scored sentiment numbers from API vendors are consumed as *numbers*, never as prose to reason over.

---

## 5. Storage

Three different jobs, three different tools:

| What | Where | Why |
|------|-------|-----|
| Code, agent prompts, skill configs | GitHub (this repo) | Versioned source of truth |
| Raw market/macro time-series | Local flat files — Parquet + DuckDB | Time-series, not semantic; DuckDB reads Parquet directly, zero infra |
| Decision trail / reasoning history / embeddings | Embeddings-in-Parquet + brute-force cosine (RT-10) | Graduate to self-hosted Qdrant only when measurably slow. Pinecone rejected |

No streaming infrastructure needed — see reaction speed below.

---

## 6. Reaction Speed / Scheduling

Assessed per bucket — none require faster than daily. Rate ETFs react the day after scheduled data drops; cat bonds move over days of cone-of-uncertainty; institutional lag is quarterly by nature.

**Conclusion: a single daily cron job covers the entire system.** No always-on process, no real-time feed infrastructure. Cheap, debuggable, backtestable.

---

## 7. Execution Layer

- **Broker: Alpaca (to be verified for Swiss residency — RT-6), fallback IBKR.** Covers stocks/ETFs/crypto (buckets 1, 3, 4). ILS (NYSE) likely tradable but thin (RT-3); KRC is UCITS/London-listed and NOT on Alpaca — bucket 2 may require IBKR regardless.
- **Sequencing:** paper-trade first → fund with a small real amount only after observing a few decision cycles → run as scheduled daily job.
- **Hard boundary:** nothing executes trades from a chat interface, regardless of permission granted in-conversation. Execution lives entirely in the script layer against the broker API, behind `execution/guard.py`.

---

## 8. Open Design Work (not yet resolved)

1. **GDELT relevance filter** — concrete severity/actor/theme threshold (Phase 3, empirical)
2. **Scenario-threading implementation** — injecting the counterfactual into each analyst's individual tool calls (Phase 2)
3. **Cat bond / ILS data feed** — confirm what's accessible free vs. paid
4. **Evaluation methodology** — REVISED per RT-4/RT-7: backtest validates mechanical layers only; LLM reasoning is evaluated forward via prediction logging + calibration scoring. Prediction log exists from Phase 0. ✅ scaffolded
5. **13F data pipeline** — scope EDGAR parsing before assuming it's a quick add
6. **Existing repo** — ✅ resolved: the pre-existing static dashboard (`index.html`) is kept as the operator-facing view; the Python package was scaffolded around it per §11.2

---

## 9. Red Team Findings (v2 review)

Adversarial review of v1, ordered by severity. RT-1, RT-4, RT-5 change the design; the rest change expectations or add guardrails.

### RT-1 — DESIGN ERROR (corrected in §3): Kronos cannot be "conditioned on a scenario"
Kronos is price-in, price-out: it tokenizes OHLCV and autoregressively samples future candles. There is no input channel for "Fed +0.1%". **Correction:** Kronos produces the *unconditional baseline distribution*; the scenario delta is estimated at the reasoning layer (historical-analog analysis from FRED + price data) and applied on top. Weaker than v1 implied, but real instead of imaginary.

### RT-2 — EPISTEMIC RISK: LLM scenario reasoning produces confident narratives, not probabilities
A plausible causal chain (rates up → NIM up → XLF up) is a story; historical data frequently disagrees. Bull and Bear are the same model wearing different hats. **Guardrails:** (a) every scenario claim must cite a checkable historical analog or a FRED-derivable number, or be labeled "narrative, unverified"; (b) standing Devil's Advocate step that finds the *opposite* historical case; (c) log every directional prediction with confidence and score calibration monthly.

### RT-3 — OVERSTATED EDGE: the cat-bond/weather thesis is weaker than v1 claimed
The secondary cat-bond market is priced by professionals watching the same free NHC feed in real time. ILS is tiny (~$25M AUM), spreads wide, ER 1.58%. **What survives:** the *seasonal* angle — spreads widen pre/early hurricane season, tighten after loss-free seasons — plus post-event dislocation. A slow, calendar-driven play matching this system's cadence. Reframe the Cat/Weather agent accordingly.

### RT-4 — BACKTEST CONTAMINATION: LLMs have seen the past
Any backtest where a frontier LLM "reacts" to a 2023–2025 event is contaminated — the model knows what happened next. **Correction:** backtesting validates the *mechanical* layers only. The reasoning layer is evaluated *forward*: paper-trade from day one, log predictions with confidence, score calibration prospectively. Accept that this takes months. The single most important expectation reset in this review.

### RT-5 — MISSING THREAT MODEL: prompt injection via the data pipeline
GDELT summaries, news text, and scraped filings flow into LLM agents that gate real-money trades. **Guardrails:** (a) all fetched text is data, never instructions — structured extraction first (`extraction/events.py`), reasoning over typed fields only; (b) the execution layer enforces hard limits *outside* the LLM (`execution/guard.py`): whitelist, size/turnover caps, no-short/no-margin — the LLM proposes, deterministic code disposes; (c) live trades above a threshold require a human confirm flag.

### RT-6 — JURISDICTION GAPS (Swiss resident, CHF base)
Verify Alpaca CH onboarding before building against it (IBKR fallback covers KRC too). Log P&L in USD and CHF — FX swings can exceed the edge at this size. Flag for own research: Swiss private capital gains vs. taxable dividend income (ILS ~8% distribution is income); professional-trader classification risk; W-8BEN for the 15% treaty rate.

### RT-7 — STATISTICS: at daily/weekly cadence, returns cannot prove anything for years
Dozens of effective independent bets annually; skill vs. luck takes years. **Success metric reframe:** (a) *calibration* — measurable within months; (b) *process quality* — did the trail cite real data, was the Devil's Advocate engaged; (c) returns vs. buy-and-hold as the long-run scoreboard, explicitly labeled underpowered in year one.

### RT-8 — COST: multi-agent frontier-LLM runs may exceed the account's expected return
**Mitigations:** (a) tiered models — cheap model for extraction, frontier only for debate/synthesis (`config/models.yaml`); (b) full graph only on shock or weekly, lightweight daily pre-check; (c) token cost logged per run as a first-class metric next to P&L.

### RT-9 — MAINTENANCE: hard-forking a fast-moving repo means drift
Depend on TradingAgents as a pinned package; keep Nighttrader-specific nodes in an overlay layer (`src/nighttrader/agents/`). Fork only if extension points prove insufficient.

### RT-10 — SIMPLIFICATION: Qdrant is likely premature
Embeddings-in-Parquet + brute-force cosine (`memory/recall.py`) until semantic recall is actually slow. Keep the decision-log schema stable so migration is trivial.

### RT-11 — KNOWN-CROWDED TRADE: 13F cloning is a published strategy
The naive 45-day-lag edge is largely arbitraged. Less crowded: combinations (13F changes contradicting sell-side sentiment; cluster analysis across filers). Institutional Lag output is one weak signal among several, never a standalone trigger.

---

## 10. Explicit Non-Goals

- No sub-second or intraday HFT competition
- No personalized investment advice generation — output is a reasoned watchlist, not a buy button
- No cloud-managed vector DB (Pinecone) at this scale
- No always-on streaming infrastructure
- No trade execution from within a chat interface, under any permission framing

---

## 11. Implementation Guide (for Claude Code)

Phase gates are hard stops — do not start a phase until the previous gate's acceptance criteria pass.

### 11.1 Stack pins

- Python 3.12 target (repo floor 3.11 for CI portability), `uv` for env/deps
- Core deps in `pyproject.toml`; heavier layers are extras keyed to phases: `kronos` (torch + huggingface_hub), `broker` (alpaca-py), `agents` (langgraph, langchain-anthropic, tradingagents pinned when Phase 2 starts)
- All inter-agent payloads are pydantic v2 models (`src/nighttrader/schemas.py`)
- Models: Haiku-class for extraction, frontier for debate/synthesis only. Names in `config/models.yaml`, never hardcoded.
- Secrets: `.env` (gitignored) + `python-dotenv`. Never in code, never in this doc, never in logs.

### 11.2 Repo layout

```
night-trader/
├── NIGHTTRADER_DESIGN.md        # this file — keep in sync with Notion
├── index.html                   # legacy macro dashboard (GitHub Pages) — operator view
├── pyproject.toml
├── config/
│   ├── universe.yaml            # THE ticker whitelist (execution hard limit, RT-5)
│   ├── limits.yaml              # position/turnover caps, no-short, no-margin, loss halt
│   └── models.yaml              # which LLM per graph node + token budget per run
├── src/nighttrader/
│   ├── schemas.py               # TypedEvent, Scenario, Prediction, Decision (§11.3)
│   ├── config.py                # validated config loaders
│   ├── data/                    # one module per source; each returns typed rows
│   ├── extraction/              # RT-5 firewall: raw text → TypedEvent only
│   ├── agents/                  # overlay nodes on TradingAgents graph (Phase 2+)
│   ├── execution/
│   │   ├── guard.py             # deterministic limits — NO LLM imports (tested)
│   │   └── broker.py            # paper default; live double-gated; guard-approval required
│   ├── memory/                  # parquet store + cosine recall
│   └── evaluation/              # prediction log + calibration (RT-4/RT-7)
├── data/                        # gitignored; parquet lake
├── scripts/
│   ├── daily_run.py             # the cron entrypoint
│   └── backfill.py
└── tests/                       # every guard rule + injection fixtures + purity check
```

### 11.3 Core schemas

See `src/nighttrader/schemas.py` — TypedEvent, Scenario, Prediction, Decision, all `extra="forbid"`, UTC-stamped, schema-versioned. The code is the authoritative definition; this doc describes intent.

### 11.4 The guard contract (RT-5, non-negotiable)

`execution/guard.py` is pure deterministic Python: no LLM imports, no network. It enforces in order: (1) ticker ∈ universe.yaml, (2) size ≤ max position, (3) daily turnover budget, (4) no shorts / no margin / gross-exposure cap, (5) daily-loss circuit breaker halts new buys, (6) live trades above threshold require human `--confirm`. Anything failing is logged with reason and NOT sent. Import purity is enforced by an AST test (static + dynamic imports). Each verdict is bound to the decision and execution context it judged (decision_id/ticker/action/live/confirmed); the broker rejects any mismatch, a live broker rejects paper-context verdicts, and a live broker cannot be constructed without the two-key rule — so no code path, including verdict reuse, can skip the guard.

### 11.5 Build phases with gates

**Phase 0 — plumbing (no LLM, no money):** repo scaffold, config, FRED + prices + parquet store, DuckDB queries, Kronos locally on one ticker. *Gate: `daily_run.py --dry` produces a features row for all bucket-1 tickers; Kronos baseline forecast plot for XLF (verify on the Mac mini — MPS).*

**Phase 1 — one-analyst thin slice + prediction log (paper only):** manual scenario + FedWatch prior, ONE analyst (Kronos baseline + historical-analog delta), guard + broker in paper mode, prediction log from the first run. *Gate: a manual "Fed +25bp" scenario produces a Decision that passes the guard and places a paper order; prediction row logged; token cost logged.*

**Phase 2 — full graph:** TradingAgents dependency wired (pin version), remaining analysts, Bull/Bear/managers, extraction firewall live, Devil's Advocate. *Gate: end-to-end daily run under the `models.yaml` token budget; injection fixtures pass; calibration report renders.*

**Phase 3 — shock detection + cat bonds:** GDELT filter (start: severity ≥ 7 AND state-level actor AND theme ∈ {conflict, monetary, disaster}), NHC ingestion, seasonal ILS logic. *Gate: replay of a known past week (mechanical layers only — RT-4) fires on the right days, silent on quiet days.*

**Phase 4 — small live capital:** only after ≥ 4 weeks of reviewed paper decisions, broker residency confirmed (RT-6), W-8BEN filed. Live flag + human confirm threshold on.

### 11.6 Still deliberately unspecified (decide during build)

- Exact GDELT threshold values — Phase 3 empirical work
- Historical-analog methodology detail — Phase 1, dumb-simple first
- Embedding model for recall — irrelevant until Phase 2+
- Whether TradingAgents' extension points suffice — discover in Phase 2, document here
