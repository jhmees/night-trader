# Design Review & Best-Practice Assessment

Reviewer role: AI systems + quantitative finance. Subject: `NIGHTTRADER_DESIGN.md`
(v2, post-red-team) and the Phase 0 scaffold implementing it. Date: 2026-07-22.

## Verdict

The design is unusually honest for an LLM-trading project. The red-team pass
already killed the four failure modes that sink most of them: conditioning a
price model on text it can't ingest (RT-1), trusting LLM backtests (RT-4),
letting news text steer execution (RT-5), and measuring success by returns on
a sample size that can't support the inference (RT-7). Those corrections are
endorsed as-is. What follows is what the doc still under-specified, and how
the scaffold resolves each point.

## Endorsed as-is (no changes)

1. **Forward-only evaluation of the LLM layer** (RT-4). Calibration + process
   quality as the near-term metric, returns as an explicitly underpowered
   long-run scoreboard, is the correct statistical posture.
2. **Guard-outside-the-LLM** (RT-5). "The LLM proposes, deterministic code
   disposes" is the only defensible architecture for LLM-gated execution.
3. **Daily cadence, no streaming** (§6). Matches the actual signal horizons;
   everything faster is cost and attack surface with no edge.
4. **Dependency, not fork** (RT-9); **no vector DB yet** (RT-10); **13F as one
   weak signal** (RT-11); **seasonal ILS reframe** (RT-3).

## Gaps found and closed in this scaffold

| # | Gap | Resolution |
|---|-----|------------|
| 1 | **Live secret committed to the public repo** — a FRED API key sat in `index.html` (and remains in git history). Directly violates §11.1. | Dashboard now takes the key via browser `localStorage` prompt. **Action for operator: rotate the key** at fred.stlouisfed.org — history rewrite isn't worth it for a free-tier key, rotation is. |
| 2 | Guard purity was stated as convention only. | Enforced by an AST test (`test_guard_import_purity`) that fails CI if `guard.py` ever imports LLM/network machinery. |
| 3 | Nothing stopped code from calling the broker without the guard. | `broker.submit()` requires a passing `GuardVerdict` and raises `GuardBypassError` otherwise — the bypass is structurally impossible, not just discouraged. |
| 4 | No-short/no-margin were YAML flags, so a one-line YAML edit (or an injected "config suggestion") could flip them. | `Limits` refuses to validate with either flag true. Enabling leverage now requires editing *code*, reviewed in git history. |
| 5 | Single-gate live mode. | Two-key rule: `NIGHTTRADER_LIVE=1` env var **and** `--live` CLI flag, plus per-order `--confirm` above the notional threshold. Three independent human actions before real money moves. |
| 6 | No drawdown brake in the limits list. | Added `daily_loss_halt_pct`: realized loss beyond −X% rejects all new buys for the day (de-risking sells still pass). Cheap, deterministic, catches feedback-loop failure days. |
| 7 | One giant dependency install (torch et al.) regardless of phase. | Extras keyed to phases (`kronos`, `broker`, `agents`); Phase 0 installs in seconds. `tradingagents` intentionally absent until Phase 2 pins an exact version. |
| 8 | Schemas allowed silent extra fields — an extractor could smuggle an `instructions` key through the firewall. | All row models are `extra="forbid"`; adversarial fixtures prove smuggled fields and out-of-bounds severity fail validation. |
| 9 | No timestamp discipline stated. | All stored rows are timezone-aware UTC (naive datetimes rejected) and stamped with `schema_version` for future migration. |
| 10 | FRED revision bias unaddressed for the historical-analog stats. | Documented in `data/fred.py`: mechanical backtests must use ALFRED vintages; forward runs may use the plain endpoint. |
| 11 | No CI. | GitHub Actions: ruff + pytest, offline, no secrets needed. The 51-test suite covers every guard rule, injection fixtures, calibration math, store idempotency, and a look-ahead test on feature computation. |
| 12 | Small-N calibration reads could mislead. | `calibration.report()` refuses to present numbers below 30 resolved predictions as signal. |

## Judgment calls (flagging, not hiding)

- **Python floor is 3.11** in `pyproject.toml` (3.12 remains the target
  runtime; CI uses 3.12). Pure portability, no semantic difference.
- **Stooq, not Yahoo, for Phase 0 prices**: keyless, stable CSV, daily bars.
  The DataFrame contract is the interface; swapping to Alpaca data in Phase 1
  touches one module.
- **The legacy dashboard stays** at the repo root (GitHub Pages serves it).
  It's a decent operator view; longer term it should read from the decision
  log instead of refetching everything client-side.
- **Bucket-3 crypto tickers** are set to IBIT/ETHA (spot ETFs) as
  placeholders — confirm the exact products you want before Phase 1.
- **`resulting brier framing`**: predictions are scored as binary
  "my direction happened at my confidence" — simple and standard. Magnitude
  scoring can come later without schema changes (`magnitude_pct` is stored).

## Still open (correctly deferred by the doc)

GDELT thresholds (Phase 3), scenario-threading mechanism (Phase 2), ILS data
feed depth, 13F parsing scope, TradingAgents extension-point sufficiency.
Plus two operator to-dos no code can close: **rotate the FRED key** and
**verify Alpaca CH onboarding / file W-8BEN** before Phase 4.

## Review loop, round 2 — adversarial findings and fixes

The scaffold above was then attacked by an independent adversarial review
(AI-systems + quant lens) whose explicit goal was to refute the endorsement
claim. It succeeded — which is the loop working. Findings, all fixed and
regression-tested in the same round:

| Sev | Finding | Fix |
|-----|---------|-----|
| Critical | **Verdict not bound to decision**: `GuardVerdict` carried no identity, so a verdict earned by a small safe XLF buy could be replayed to submit a 100% off-universe order — defeating the firewall without ever "skipping" the guard. | Verdict now carries `decision_id`/`ticker`/`action` plus the `live`/`human_confirmed` context it was judged under; the broker raises `GuardBypassError` on any mismatch. Tested (verdict reuse, ticker swap, genuine pairing). |
| Important | **Live gates were conventions, not enforcement**: the two-key rule was a helper the live broker never called, and a paper-context verdict could gate a live order. | `AlpacaBroker(paper=False)` refuses to construct without both keys (checked before any SDK import, so it's testable); live submission requires a verdict evaluated with `live=True`. Tested. |
| Important | **DuckDB injection** via on-disk category dir names interpolated into `CREATE VIEW`. | Category names validated against `[A-Za-z0-9_]+` on write and skipped on read; path quoting escaped. Tested with a hostile directory planted on disk. |
| Important | **DataFrame-path rows lacked `schema_version`/`ts`** — the exact rows Phase 0 writes — contradicting claim #9; empty DataFrames wrote silently. | Both stamps injected on the DataFrame path; empty frames refused. Tested. |
| Important | **Look-ahead test was a tautology** (compared a call to itself). | `compute_features` gained an `as_of` parameter; the test now appends corrupted future bars and asserts the as-of row is unchanged. |
| Minor | Purity test missed dynamic imports (`__import__`, `importlib`, `eval`). | AST check extended to call nodes. |
| Minor | Reliability bins fitted to the observed range → monthly tables not comparable. | Bins fixed on [0,1]; tested with mixed confidences. |
| Minor | `daily_run` minted a fresh run_id per invocation, so same-day re-runs appended duplicates despite the "idempotent" claim. | run_id is now deterministic per UTC day; a re-run overwrites its own file. |
| Minor | Calibration report printed sub-threshold numbers with a caveat ("labels rather than refuses"). | Below 30 resolved, numbers are withheld entirely. Tested. |

The reviewer confirmed the guard rule arithmetic (sequential clipping,
sell/turnover symmetry, loss-halt asymmetry, boundary rejections), the
config no-leverage invariant, the schema firewall, and the injection→guard
fixtures as genuinely sound.

## Expert sign-off criteria used

- No path from untrusted text to an order without passing typed validation
  and the deterministic guard. ✅ (tested, including adversarial fixtures)
- No path to live trading without multiple explicit human actions. ✅
- Evaluation method matches the statistics of the signal cadence. ✅
- Every stored artifact is replayable and auditable (append-only parquet,
  write-ahead decision logging, raw-text archive by reference). ✅
- Cost is a first-class metric (`token_cost_usd` on every Decision;
  per-run budget in `models.yaml`). ✅
