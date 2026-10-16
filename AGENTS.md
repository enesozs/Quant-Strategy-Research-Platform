# AGENTS.md

Guidance for coding agents working in this repository. The README describes the product; this file covers how to work on it.

## Environment

- Use the project interpreter: `.venv/bin/python`. The `python` on PATH may belong to another project's venv and lack `statsmodels`.
- Tests: `.venv/bin/python -m pytest -q` (fast, offline, synthetic data).
- Web app: `make dev` (API :8020, UI :5190; ports avoid projects 05/06), `make serve` (built UI + API on :8020), `make test`.
- Web checks: `cd web && npx tsc -b && npm run lint && npm test && npm run build`.
- Legacy Streamlit app: `make streamlit`. Smoke test without a browser: `streamlit.testing.v1.AppTest.from_file("app.py")`, set `session_state["analysis_mode"]`, click the page's run button.
- Docker: `docker build -t strategy-lab .` (web build + `requirements-api.txt`); `render.yaml` deploys it on Render.
- Browser tests: Playwright lives in project 06's venv (`../06-financial-terminal/backend/.venv/bin/python`), using system Chrome.

## Architecture

- Core research modules (no Streamlit imports): `backtester.py`, `metrics.py`, `strategies/`, `optimization.py`, `validation.py`, `comparison.py`, `pairs_trading_*.py`.
- Web API: `api/` (FastAPI; `main.py` routes, `schemas.py` Pydantic models, `services.py` core calls, `serialize.py` NaN→null/ISO dates, `cache.py` download cache). `api/CONTRACT.md` is the single source of truth for request/response shapes; change it first.
- Web UI: `web/` (React 19, Vite, Tailwind v4, TanStack Query, ECharts). `src/api/types.ts` mirrors the contract; all formatting lives in `src/lib/format.ts`.
- Legacy UI pages: `*_app.py`, dispatched from `app.py`. Keep research logic out of these.
- `strategies/__init__.py` is the registry: implementation, metadata (powers forms and the Strategy Guide), default parameters, optimization grids. Every integer parameter is a window length; `get_lookback_observations` relies on that.

## Invariants (do not break)

- **Signal timing:** a signal computed on day t sets the position for day t+1 (`shift(1)` in `run_backtest` and `run_weighted_pair_backtest`).
- **Costs:** one-way proportional cost on |change in exposure|; Buy and Hold pays one entry cost.
- **Warm windows:** use `run_strategy_on_window` to score a sub-period. Indicators warm up on earlier rows; the portfolio starts flat on the row before `evaluation_start`, and that row's return is neutralized so neither leg earns it.
- **Common burn-in:** `optimize_strategy` scores every candidate from the same `evaluation_start` (after the grid's longest lookback). Validation training metrics reuse it. Don't score candidates from the first row of a sample.
- **No selection look-ahead:** pair discovery ranks on the opening formation window only.
- **Pairs signal/trade bookkeeping:** `exit_reason` is recorded on the signal row; the position goes flat one row later, and that row carries the exit cost. `extract_trades` depends on this.
- `apply_strategy` merges partial parameters over defaults.
- **Cash and financing:** `cash_rate` (idle-cash yield) is separate from `risk_free_rate` (Sharpe only) and is threaded through every backtest, optimization, validation and comparison entry point. Interest lives in `gross_strategy_return`, which walk-forward stitching relies on. Pairs use `cash_rate` + `borrow_fee`.
- `metrics.calculate_performance_metrics` returns `calmar_ratio`; `OptimizationResults` carries `probabilistic_sharpe_ratio` and `deflated_sharpe_ratio`.
- Pairs method names live in `pairs_trading_core` (`METHOD_*`); the sensitivity optimizer is `pairs_trading_sensitivity.py`; multi-pair OOS portfolios are `pairs_trading_portfolio.py`.

## Next steps

- The Streamlit UI is kept as a reference; new features land in the web app only.
- Background jobs with progress (SSE) for long optimizations.
- Cash and borrow rates from a rate history.
- Multi-asset portfolio engine (signals × allocator from project 03).

## Workflow

- Ask the user before committing.
