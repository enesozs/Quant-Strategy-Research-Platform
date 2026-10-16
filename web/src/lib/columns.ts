// Column formatting for the generic `Row[]` tables the API returns. Kinds are inferred from
// column names (the backend's pandas column names), with objective-valued columns formatted in
// the units of the selected objective.

import { humanize, METRIC_KINDS, type ValueKind } from './format'

const LABELS: Record<string, string> = {
  display_name: 'Strategy',
  strategy: 'Strategy',
  annualized_volatility: 'Volatility',
  sharpe_ratio: 'Sharpe',
  calmar_ratio: 'Calmar',
  max_drawdown: 'Max DD',
  total_return: 'Total return',
  final_value: 'Final value',
  average_exposure: 'Exposure',
  return_rank: 'Return #',
  cagr_rank: 'CAGR #',
  sharpe_rank: 'Sharpe #',
  volatility_rank: 'Vol #',
  drawdown_rank: 'DD #',
  rebalancing_days: 'Rebal. days',
  absolute_oos_degradation: 'OOS degradation',
  relative_oos_degradation: 'Degradation %',
  bonferroni_pvalue: 'Bonferroni p',
  cointegration_pvalue: 'Coint. p',
  adf_pvalue: 'ADF p',
  half_life_days: 'Half-life (d)',
  return_correlation: 'Return corr.',
  price_correlation: 'Price corr.',
  asset_a: 'A',
  asset_b: 'B',
  beta_coefficient_of_variation: 'Beta CV',
  valid_beta_share: 'Valid beta %',
  maximum_abs_zscore: 'Max |z|',
  entry_zscore: 'Entry z',
  net_pair_return: 'Net return',
  gross_pair_return: 'Gross return',
  long_leg_contribution: 'Long leg',
  short_leg_contribution: 'Short leg',
  transaction_cost: 'Costs',
  beats_default_share: 'Beats default',
}

export function columnLabel(key: string): string {
  if (LABELS[key]) return LABELS[key]
  for (const prefix of ['test_', 'stitched_']) {
    if (key.startsWith(prefix) && LABELS[key.slice(prefix.length)])
      return `${humanize(prefix)} ${LABELS[key.slice(prefix.length)].toLowerCase()}`
  }
  return humanize(key)
}

/**
 * Infer how a column should be formatted.
 * @param objectiveFormat units of `*_objective` and absolute degradation columns.
 */
export function inferKind(
  key: string,
  sample: unknown,
  objectiveFormat: 'percent' | 'ratio' = 'ratio',
): ValueKind {
  if (typeof sample === 'boolean') return 'boolean'
  const k = key.toLowerCase()
  const base = k.replace(/^(test_|training_|stitched_|default_|best_|raw_|robust_)/, '')
  if (k.includes('date') || /(^|_)(start|end)$/.test(k)) return 'date'
  if (typeof sample === 'string') return 'text'
  if (k.includes('pvalue') || k.endsWith('_p')) return 'pvalue'
  if (k.includes('objective') || k.startsWith('absolute_') || k.includes('_absolute_'))
    return objectiveFormat === 'percent' ? 'percent' : 'ratio'
  if (k.includes('relative') || k.includes('share') || k.includes('gain_pct')) return 'percent'
  if (METRIC_KINDS[base]) return METRIC_KINDS[base]
  if (k.endsWith('_rank') || k === 'rank' || k === 'fold' || k === 'folds') return 'integer'
  if (
    k === 'trades' ||
    k.includes('observations') ||
    k.includes('count') ||
    k.includes('crossings') ||
    k.endsWith('_days') ||
    k === 'holding_days'
  )
    return k.includes('half_life') ? 'number' : 'integer'
  if (k.includes('correlation')) return 'ratio'
  if (k.includes('return') || k.includes('contribution') || k === 'transaction_cost')
    return 'percent'
  if (
    k.includes('correlation') ||
    k.includes('zscore') ||
    k.includes('beta') ||
    k.includes('ratio')
  )
    return 'ratio'
  return 'number'
}
