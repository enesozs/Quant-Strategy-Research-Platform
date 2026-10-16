// Mirrors api/CONTRACT.md (v1). The contract is the source of truth: change it first, then here.
// JSON is snake_case; rates and returns are decimal fractions; dates are ISO YYYY-MM-DD strings;
// non-finite numbers arrive as null.

export type Num = number | null

/** Columnar time series: every column has one value per date. */
export interface TimeSeries {
  dates: string[]
  columns: Record<string, Num[]>
}

/** Any metric may be null (e.g. Sharpe of a strategy that never trades). */
export interface Metrics {
  total_return: Num
  cagr: Num
  annualized_volatility: Num
  sharpe_ratio: Num
  /** Negative fraction; closer to 0 is better. */
  max_drawdown: Num
  calmar_ratio: Num
  final_value?: Num
  rebalancing_days?: Num
  turnover?: Num
  average_exposure?: Num
}

/** One table row. */
export type Row = Record<string, string | number | boolean | null>

/** Portfolio assumptions shared by every single-asset request. */
export interface MarketRequest {
  ticker: string
  start_date: string
  end_date: string
  /** Default 10000. */
  initial_capital?: number
  /** Default 10, one-way. */
  transaction_cost_bps?: number
  /** Default 0.0, annual, used for Sharpe. */
  risk_free_rate?: number
  /** Default true: idle cash earns risk_free_rate. */
  cash_earns_risk_free?: boolean
}

export type Objective =
  | 'sharpe_ratio'
  | 'total_return'
  | 'cagr'
  | 'annualized_volatility'
  | 'max_drawdown'
  | 'calmar_ratio'

export type ParameterValue = number
export type Parameters = Record<string, ParameterValue>
export type Grid = Record<string, ParameterValue[]>

// ---------------------------------------------------------------------------------------------
// GET /api/health, GET /api/meta

export interface Health {
  status: 'ok'
}

export interface ParameterSpec {
  label: string
  type: 'int' | 'float'
  default: number
  min: number
  max: number
  step: number
  format?: 'percent'
}

export interface StrategyMeta {
  key: string
  display_name: string
  family: string
  subtype: string
  features: string[]
  signal_style: string
  best_suited_for: string
  description: string
  thesis: string
  favorable_environment: string
  unfavorable_environment: string
  main_risks: string
  optimization_notes: string
  validation_focus: string
  related_strategies: string[]
  parameters: Record<string, ParameterSpec>
  default_grid: Grid
  /** Raw combinations in default_grid. */
  grid_size: number
}

export interface ObjectiveMeta {
  key: Objective
  label: string
  higher_is_better: boolean
  format: 'percent' | 'ratio'
}

export interface PairsMethodMeta {
  key: string
  label: string
  description: string
}

export interface Meta {
  strategies: StrategyMeta[]
  objectives: ObjectiveMeta[]
  pairs_methods: PairsMethodMeta[]
  universe_presets: Record<string, string[]>
}

// ---------------------------------------------------------------------------------------------
// POST /api/backtest

export interface BacktestRequest extends MarketRequest {
  strategy: string
  /** Missing parameters use defaults. */
  parameters?: Parameters
}

export interface BacktestResponse {
  strategy: string
  parameters: Parameters
  /** Includes rebalancing_days, turnover, average_exposure. */
  metrics: Metrics
  /** Buy and Hold. */
  benchmark_metrics: Metrics
  /** close, position, strategy_equity, buy_hold_equity, strategy_drawdown, buy_hold_drawdown. */
  series: TimeSeries
  /** Indicator columns on the price scale (moving averages, bands, channels). */
  overlays: TimeSeries
  /** Indicator columns on their own scale (rsi, cci, adx, macd, ...). */
  oscillators: TimeSeries
}

// ---------------------------------------------------------------------------------------------
// POST /api/compare

export interface CompareRequest extends MarketRequest {
  use_optimized_parameters?: boolean
  objective?: Objective
}

export interface CompareResponse {
  /** True when optimized parameters were used. */
  in_sample: boolean
  /** One per strategy: strategy, display_name, family, parameters (string), metric columns,
   * trades, turnover, average_exposure, return_rank, cagr_rank, sharpe_rank, volatility_rank,
   * drawdown_rank. */
  rows: Row[]
  benchmark: Metrics
  /** One column per strategy key, plus "buy_hold". */
  equity: TimeSeries
}

// ---------------------------------------------------------------------------------------------
// POST /api/optimize

export type OptimizeMode = 'predefined' | 'custom' | 'coarse_to_fine'

export interface OptimizeRequest extends MarketRequest {
  strategy: string
  objective?: Objective
  mode?: OptimizeMode
  /** Required for custom. Grids above 5,000 raw combinations are rejected with 422. */
  grid?: Grid
  refinement_points?: number
}

export interface Heatmap {
  x_parameter: string
  y_parameter: string
  x_values: number[]
  y_values: number[]
  /** z[y][x] = best objective over the other parameters. */
  z: Num[][]
}

export interface ProfilePoint {
  value: number
  best: Num
  median: Num
}

export interface OptimizeStages {
  broad_combinations: number
  refined_combinations: number
  broad_best_parameters: Parameters
  refined_grid: Grid
}

export interface OptimizeResponse {
  objective: Objective
  /** First scored date (common burn-in). */
  evaluation_start: string
  combinations_tested: number
  best_parameters: Parameters
  best_metrics: Metrics
  default_parameters: Parameters
  default_metrics: Metrics
  optimization_gain: Num
  relative_optimization_gain: Num
  /** P(true Sharpe > 0) for the raw optimum. */
  probabilistic_sharpe_ratio: Num
  /** Same, after accounting for every trial. */
  deflated_sharpe_ratio: Num
  /** All OptimizationRobustnessDiagnostics fields (parameter dicts serialised as objects). */
  robustness: Row
  /** Ranked, best first, at most 500 rows. */
  results: Row[]
  /** Only for strategies with >= 2 grid parameters. */
  heatmap: null | Heatmap
  profiles: Record<string, ProfilePoint[]>
  /** coarse_to_fine only. */
  stages?: OptimizeStages
}

// ---------------------------------------------------------------------------------------------
// POST /api/validate/split, POST /api/validate/walk-forward

export interface SplitRequest extends MarketRequest {
  strategy: string
  objective?: Objective
  split_date: string
  grid?: Grid
}

export interface ParameterSetResult {
  /** "Default parameters", "Raw optimum", "Robust candidate". */
  label: string
  parameters: Parameters
  training_metrics: Metrics
  test_metrics: Metrics
}

export interface SplitResponse {
  split_date: string
  training_evaluation_start: string
  robustness_label: string
  parameter_sets: ParameterSetResult[]
  benchmark: { training_metrics: Metrics; test_metrics: Metrics }
  /** build_validation_summary output. */
  summary: Row[]
  /** One column per parameter set + "buy_hold". */
  test_equity: TimeSeries
}

export type WindowType = 'expanding' | 'rolling'

export interface WalkForwardRequest extends MarketRequest {
  strategy: string
  objective?: Objective
  window_type?: WindowType
  initial_training_years?: number
  test_window_years?: number
}

export interface WalkForwardResponse {
  /** Fold summary table. */
  folds: Row[]
  parameter_history: Row[]
  /** Aggregate summary table. */
  aggregate: Row[]
  stitched_equity: TimeSeries
}

// ---------------------------------------------------------------------------------------------
// Pairs

export interface PairsAssumptions {
  start_date: string
  end_date: string
  initial_capital?: number
  transaction_cost_bps?: number
  risk_free_rate?: number
  cash_earns_risk_free?: boolean
  /** Annual fee on the short leg, default 0.0. */
  borrow_fee?: number
}

export type PairsMethod = 'distance' | 'cointegration' | 'kalman'

/** Any method-specific builder argument (entry_zscore, exit_zscore, stop_zscore,
 * maximum_holding_days, formation_years, trading_months, warmup_window, zscore_window, ...). */
export type PairsParams = Record<string, number | boolean>

export interface PairsResearchRequest extends PairsAssumptions {
  method: PairsMethod
  ticker_a: string
  ticker_b: string
  params?: PairsParams
}

export interface PairsResearchResponse {
  method: PairsMethod
  ticker_a: string
  ticker_b: string
  metrics: Metrics
  /** 50/50 long both legs. */
  benchmark_metrics: Metrics
  return_correlation: Num
  price_correlation: Num
  /** normalized_a, normalized_b (rebased to 1), spread, spread_zscore, pair_position,
   * strategy_equity, benchmark_equity, strategy_drawdown, and hedge_beta / dynamic_beta when
   * available. */
  series: TimeSeries
  trades: Row[]
  exit_reasons: Record<string, number>
  diagnostics: Row[]
}

/** In-sample. */
export interface PairsSensitivityResponse {
  rows: Row[]
  recommended_params: PairsParams
}

export interface PairsUniverseRequest extends PairsAssumptions {
  method: PairsMethod
  tickers: string[]
  formation_years?: number
  top_n?: number
  params?: PairsParams
}

export interface PairsDiscoverResponse {
  selection_start: string
  selection_end: string
  rows: Row[]
}

export interface PairsPortfolioResponse {
  selection_start: string
  selection_end: string
  discovery: Row[]
  pair_summary: Row[]
  metrics: Metrics
  average_pair_correlation: Num
  /** portfolio_equity, portfolio_drawdown, and "equity::<A/B>" per pair. */
  series: TimeSeries
}

/** Error body for 422 / 502. */
export interface ApiErrorBody {
  detail: string
}
