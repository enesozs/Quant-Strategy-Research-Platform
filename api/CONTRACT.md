# Web API contract (v1)

The FastAPI backend (`api/`) wraps the core research modules at the repository root. The React
frontend (`web/`) talks to it only through these endpoints. Both sides must follow this file;
change it first if the contract has to move.

- Base URL: `/api`. Dev ports: API `8020`, web `5190` (Vite proxies `/api` → `8020`).
- JSON uses **snake_case**. All rates and returns are **decimal fractions** (`0.12` = 12%),
  never percentages. Dates are ISO `YYYY-MM-DD` strings.
- Non-finite numbers (NaN, ±inf) are serialised as `null`.
- Errors: `422 {"detail": "<human-readable message>"}` for invalid input or a research
  `ValueError` (e.g. sample too short); `502 {"detail": ...}` when market data cannot be
  downloaded. The frontend shows `detail` verbatim.

## Shared shapes

```ts
type Num = number | null

// Columnar time series: every column has one value per date.
interface TimeSeries {
  dates: string[]
  columns: Record<string, Num[]>
}

// Any metric may be null (e.g. Sharpe of a strategy that never trades).
interface Metrics {
  total_return: Num
  cagr: Num
  annualized_volatility: Num
  sharpe_ratio: Num
  max_drawdown: Num          // negative fraction, closer to 0 is better
  calmar_ratio: Num
  final_value?: Num
  rebalancing_days?: Num
  turnover?: Num
  average_exposure?: Num
}

type Row = Record<string, string | number | boolean | null>   // one table row

// Portfolio assumptions shared by every single-asset request.
interface MarketRequest {
  ticker: string
  start_date: string
  end_date: string
  initial_capital?: number           // default 10000
  transaction_cost_bps?: number      // default 10, one-way
  risk_free_rate?: number            // default 0.0, annual, used for Sharpe
  cash_earns_risk_free?: boolean     // default true: idle cash earns risk_free_rate
}

type Objective =
  'sharpe_ratio' | 'total_return' | 'cagr' | 'annualized_volatility' | 'max_drawdown' | 'calmar_ratio'

type ParameterValue = number
type Parameters = Record<string, ParameterValue>
type Grid = Record<string, ParameterValue[]>
```

## Endpoints

### `GET /api/health` → `{ "status": "ok" }`

### `GET /api/meta`
Everything the UI needs to build forms and the Strategy Guide.
```ts
{
  strategies: Array<{
    key: string, display_name: string, family: string, subtype: string,
    features: string[], signal_style: string, best_suited_for: string,
    description: string, thesis: string,
    favorable_environment: string, unfavorable_environment: string,
    main_risks: string, optimization_notes: string, validation_focus: string,
    related_strategies: string[],
    parameters: Record<string, {
      label: string, type: 'int' | 'float', default: number,
      min: number, max: number, step: number, format?: 'percent'
    }>,
    default_grid: Grid,
    grid_size: number              // raw combinations in default_grid
  }>,
  objectives: Array<{ key: Objective, label: string, higher_is_better: boolean,
                      format: 'percent' | 'ratio' }>,
  pairs_methods: Array<{ key: string, label: string, description: string }>,
  universe_presets: Record<string, string[]>
}
```

### `POST /api/backtest`
Body: `MarketRequest & { strategy: string, parameters?: Parameters }` (missing parameters use defaults).
```ts
{
  strategy: string, parameters: Parameters,
  metrics: Metrics,                 // includes rebalancing_days, turnover, average_exposure
  benchmark_metrics: Metrics,       // Buy and Hold
  series: TimeSeries,               // close, position, strategy_equity, buy_hold_equity,
                                    // strategy_drawdown, buy_hold_drawdown
  overlays: TimeSeries,             // indicator columns on the price scale (moving averages, bands, channels)
  oscillators: TimeSeries           // indicator columns on their own scale (rsi, cci, adx, macd, ...)
}
```

### `POST /api/compare`
Body: `MarketRequest & { use_optimized_parameters?: boolean, objective?: Objective }`.
```ts
{
  in_sample: boolean,               // true when optimized parameters were used
  rows: Row[],                      // one per strategy: strategy, display_name, family, parameters (string),
                                    // metric columns, trades, turnover, average_exposure,
                                    // return_rank, cagr_rank, sharpe_rank, volatility_rank, drawdown_rank
  benchmark: Metrics,
  equity: TimeSeries                // one column per strategy key, plus "buy_hold"
}
```

### `POST /api/optimize`
Body: `MarketRequest & { strategy: string, objective?: Objective,
  mode?: 'predefined' | 'custom' | 'coarse_to_fine', grid?: Grid, refinement_points?: number }`.
`grid` is required for `custom`. Grids above 5,000 raw combinations are rejected with 422.
```ts
{
  objective: Objective,
  evaluation_start: string,          // first scored date (common burn-in)
  combinations_tested: number,
  best_parameters: Parameters, best_metrics: Metrics,
  default_parameters: Parameters, default_metrics: Metrics,
  optimization_gain: Num, relative_optimization_gain: Num,
  probabilistic_sharpe_ratio: Num,   // P(true Sharpe > 0) for the raw optimum
  deflated_sharpe_ratio: Num,        // same, after accounting for every trial
  robustness: Row,                   // all OptimizationRobustnessDiagnostics fields
                                     // (parameter dicts serialised as objects)
  results: Row[],                    // ranked, best first, at most 500 rows
  heatmap: null | {                  // only for strategies with >= 2 grid parameters
    x_parameter: string, y_parameter: string,
    x_values: number[], y_values: number[],
    z: Num[][]                       // z[y][x] = best objective over the other parameters
  },
  profiles: Record<string, Array<{ value: number, best: Num, median: Num }>>,
  stages?: { broad_combinations: number, refined_combinations: number,
             broad_best_parameters: Parameters, refined_grid: Grid }   // coarse_to_fine only
}
```

### `POST /api/validate/split`
Body: `MarketRequest & { strategy: string, objective?: Objective, split_date: string, grid?: Grid }`.
```ts
{
  split_date: string, training_evaluation_start: string,
  robustness_label: string,
  parameter_sets: Array<{ label: string, parameters: Parameters,
                          training_metrics: Metrics, test_metrics: Metrics }>,
                    // labels: "Default parameters", "Raw optimum", "Robust candidate"
  benchmark: { training_metrics: Metrics, test_metrics: Metrics },
  summary: Row[],                    // build_validation_summary output
  test_equity: TimeSeries            // one column per parameter set + "buy_hold"
}
```

### `POST /api/validate/walk-forward`
Body: `MarketRequest & { strategy: string, objective?: Objective,
  window_type?: 'expanding' | 'rolling', initial_training_years?: number, test_window_years?: number }`.
```ts
{
  folds: Row[],                      // fold summary table
  parameter_history: Row[],
  aggregate: Row[],                  // aggregate summary table
  stitched_equity: TimeSeries
}
```

### Pairs

Shared body:
```ts
interface PairsAssumptions {
  start_date: string, end_date: string,
  initial_capital?: number, transaction_cost_bps?: number,
  risk_free_rate?: number, cash_earns_risk_free?: boolean,
  borrow_fee?: number                // annual fee on the short leg, default 0.0
}
type PairsMethod = 'distance' | 'cointegration' | 'kalman'
// params: any method-specific builder argument (entry_zscore, exit_zscore, stop_zscore,
// maximum_holding_days, formation_years, trading_months, warmup_window, zscore_window, ...).
```

#### `POST /api/pairs/research`
Body: `PairsAssumptions & { method: PairsMethod, ticker_a: string, ticker_b: string, params?: object }`.
```ts
{
  method: PairsMethod, ticker_a: string, ticker_b: string,
  metrics: Metrics, benchmark_metrics: Metrics,   // benchmark: 50/50 long both legs
  return_correlation: Num, price_correlation: Num,
  series: TimeSeries,   // normalized_a, normalized_b (rebased to 1), spread, spread_zscore,
                        // pair_position, strategy_equity, benchmark_equity, strategy_drawdown,
                        // and hedge_beta / dynamic_beta when available
  trades: Row[],
  exit_reasons: Record<string, number>,
  diagnostics: Row[]
}
```

#### `POST /api/pairs/sensitivity`
Same body as research. → `{ rows: Row[], recommended_params: object }` (in-sample).

#### `POST /api/pairs/discover`
Body: `PairsAssumptions & { method: PairsMethod, tickers: string[], formation_years?: number,
  top_n?: number, params?: object }`.
→ `{ selection_start: string, selection_end: string, rows: Row[] }`

#### `POST /api/pairs/portfolio`
Body: same as discover.
```ts
{
  selection_start: string, selection_end: string,
  discovery: Row[], pair_summary: Row[],
  metrics: Metrics, average_pair_correlation: Num,
  series: TimeSeries     // portfolio_equity, portfolio_drawdown, and "equity::<A/B>" per pair
}
```

## Backend implementation notes (clarifications, no shape changes)

- 422 `detail` for body-validation errors is one string: `"<field>: <message>; ..."`.
  Unknown `/api/*` paths return `404 {"detail": ...}` (never the SPA's index.html).
- `/compare` `rows` also contain the Buy and Hold benchmark row
  (`strategy: "buy_and_hold"`, `family: "Benchmark"`); it is ranked with the strategies.
  Rows carry a few extra core columns (`features`, `optimization_*`, `final_value`).
- `/optimize` `coarse_to_fine`: `best_*`, `results`, `heatmap`, `profiles`, `robustness`
  and the Sharpe probabilities come from the refined stage; `combinations_tested` is
  broad + refined. The refined grid is also capped at 5,000 combinations.
  `heatmap` axes are the two grid parameters with the most distinct tested values
  (x has the most); for `annualized_volatility` z is the minimum over the other parameters.
  `profiles[].best` is the best value in the objective's direction.
- Parameters and grid values are checked against the strategy's `min`/`max`, and int
  parameters must be whole numbers (otherwise 422).
- `/validate/walk-forward` uses the strategy's predefined grid.
- Pairs `params` are checked against the method's builder arguments; unknown keys → 422.
  `/pairs/discover` and `/pairs/portfolio` also accept `discover_pairs` arguments
  (e.g. `minimum_observations`, `maximum_cointegration_pvalue`). `top_n` defaults:
  discover 10, portfolio 5.
- Pairs `series` also includes `benchmark_drawdown`. Cointegration's `hedge_beta` is
  the per-window OLS beta; Kalman has both `dynamic_beta` (filter) and `hedge_beta`
  (the beta locked in at entry).
- Discover/portfolio drop tickers whose download fails; 502 only if fewer than two remain.
- `/optimize` `robustness` is a `Row` in name only: `boundary_parameters` is a string array and
  `robust_candidate_parameters` is a `Parameters` object. Read those two fields as such.
- `/compare` rows: `strategy` is the registry key (or `buy_and_hold`), `display_name` the label.
- `/validate/split` `test_equity` columns are the parameter-set labels ("Default parameters",
  "Raw optimum", "Robust candidate") plus `buy_hold`.
- `/pairs/sensitivity` `recommended_params` echoes every builder argument, including
  `rehedge_daily` and `trading_start`; clients should apply only the parameters they expose.
- Relative out-of-sample degradation uses the same per-objective scale floor as the optimizer's
  robustness diagnostics, so it stays meaningful when the training objective is near zero.
