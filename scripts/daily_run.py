"""Daily cron entrypoint (design §6: one daily job covers the whole system).

Phase 0 scope: fetch prices + macro, compute features, write one parquet row
per bucket-1 ticker. No LLM, no orders. Later phases extend this same
entrypoint; the cron line never changes.

Usage:
    uv run python scripts/daily_run.py --dry            # features only
    uv run python scripts/daily_run.py --dry --no-fred  # skip FRED (no key)

Gate check (design §11.5 Phase 0): --dry produces a features row for all
bucket-1 tickers.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

import httpx
from dotenv import load_dotenv

from nighttrader.config import load_limits, load_universe
from nighttrader.data import fred, prices
from nighttrader.memory import store


def main() -> int:
    parser = argparse.ArgumentParser(description="Nighttrader daily run")
    parser.add_argument("--dry", action="store_true", help="no orders, features only")
    parser.add_argument("--no-fred", action="store_true", help="skip FRED macro snapshot")
    parser.add_argument(
        "--publish", action="store_true",
        help="write data.json for the GitHub Pages dashboard after the run",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="request live mode (also requires NIGHTTRADER_LIVE=1; Phase 4)",
    )
    args = parser.parse_args()
    load_dotenv()

    if args.live:
        print("live mode is Phase 4 work and not implemented; refusing.", file=sys.stderr)
        return 2

    # Deterministic per UTC day: re-running the cron overwrites its own file
    # instead of appending a duplicate (idempotent re-runs, store contract).
    run_id = f"run-{datetime.now(UTC):%Y%m%d}"
    universe = load_universe()
    load_limits()  # fail fast on a malformed limits file, even in dry runs
    tickers = universe.tickers_for(1)
    print(f"[{run_id}] bucket-1 tickers: {', '.join(tickers)}")

    rows, failures = [], []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for t in tickers:
            try:
                df = prices.fetch_daily(t, client=client)
                rows.append(prices.compute_features(df, t))
                print(f"  {t}: {len(df)} bars, close {rows[-1]['close']:.2f}")
            except Exception as e:  # noqa: BLE001 - one bad ticker must not kill the run
                failures.append(t)
                print(f"  {t}: FAILED — {e}", file=sys.stderr)

        macro = None
        if not args.no_fred:
            try:
                macro = fred.macro_snapshot(client=client)
                print(f"  macro: 2s10s={macro['curve_2s10s']}, VIX={macro['VIXCLS']}")
            except fred.FredError as e:
                print(f"  macro: skipped — {e}", file=sys.stderr)

    if rows:
        import pandas as pd

        path = store.write_rows(pd.DataFrame(rows), "features", run_id)
        print(f"[{run_id}] wrote {len(rows)} feature rows -> {path}")
    if macro:
        import pandas as pd

        path = store.write_rows(pd.DataFrame([macro]), "macro", run_id)
        print(f"[{run_id}] wrote macro snapshot -> {path}")

    if args.publish:
        from nighttrader.dashboard import write_dashboard_json

        out = write_dashboard_json()
        print(f"[{run_id}] published dashboard payload -> {out}")
        print(f"[{run_id}] (commit + push data.json so GitHub Pages picks it up)")

    if failures:
        print(f"[{run_id}] FAILURES: {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"[{run_id}] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
