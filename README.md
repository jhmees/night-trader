# Night Trader — Dark Echo Macro Signal Dashboard

Live macro signal dashboard combining:
- **Faber 10-month moving average** signals for GLD, TLT, XLE, EEM, ITA
- **FRED macro indicators**: yield curve, VIX, HY credit spreads, Fed funds rate
- **Crypto ripple monitor**: BTC/ETH as leading risk sentiment indicators

## Strategy
Based on Meb Faber's GTAA framework. Monthly check on last trading day.
Hold assets above 10M MA. Rotate based on macro causal maps.

## Live dashboard
👉 [Open dashboard](https://jhmees.github.io/night-trader/)

## Setup
Replace `FRED_KEY` in `index.html` with your FRED API key from [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html).

## Files
- `index.html` — live dashboard (FRED + Yahoo Finance + CoinGecko)
- `README.md` — this file
