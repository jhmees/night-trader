"""Overlay agent nodes on the TradingAgents graph (design §3, RT-9).

Phase 2+ work. These modules hold the Nighttrader-specific nodes so the
upstream `tradingagents` package stays an untouched pinned dependency:

- ``scenario``          — scenario threading + market-implied priors
- ``shock_detector``    — GDELT relevance filter (Phase 3)
- ``institutional_lag`` — 13F deltas as one weak signal (RT-11)
- ``cat_weather``       — seasonal ILS spread cycles, NOT landfall calls (RT-3)
"""
