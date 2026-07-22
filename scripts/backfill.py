"""Backfill full price history for the whole universe into the parquet lake.

Run once at setup, and again if the lake is rebuilt. History is stored raw
(one file per ticker under data/raw_prices/) so features can always be
recomputed without refetching.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

from nighttrader.config import load_universe
from nighttrader.data import prices
from nighttrader.memory.store import DATA_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill daily price history")
    parser.add_argument("--tickers", nargs="*", help="subset; default = whole universe")
    args = parser.parse_args()

    universe = load_universe()
    tickers = args.tickers or sorted(universe.all_tickers)
    out_dir = Path(DATA_ROOT) / "raw_prices"
    out_dir.mkdir(parents=True, exist_ok=True)

    failed = []
    stamp = datetime.now(UTC).date().isoformat()
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for t in tickers:
            try:
                df = prices.fetch_daily(t, client=client)
                path = out_dir / f"{t}.parquet"
                df.assign(fetched_on=stamp).to_parquet(path)
                print(f"{t}: {len(df)} bars -> {path}")
            except Exception as e:  # noqa: BLE001
                failed.append(t)
                print(f"{t}: FAILED — {e}", file=sys.stderr)
    if failed:
        print(f"failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
