import type { Meta, Objective, ObjectiveMeta, Parameters, StrategyMeta } from '@/api/types'
import { formatObjective, isNum } from './format'

export function findStrategy(meta: Meta, key: string): StrategyMeta {
  return meta.strategies.find((s) => s.key === key) ?? meta.strategies[0]
}

export function findObjective(meta: Meta, key: Objective): ObjectiveMeta {
  return (
    meta.objectives.find((o) => o.key === key) ?? {
      key,
      label: key,
      higher_is_better: key !== 'annualized_volatility',
      format: key === 'sharpe_ratio' || key === 'calmar_ratio' ? 'ratio' : 'percent',
    }
  )
}

export function objectiveFormatter(objective: ObjectiveMeta) {
  return (value: number) => formatObjective(objective.format, value)
}

export function defaultParameters(strategy: StrategyMeta): Parameters {
  return Object.fromEntries(
    Object.entries(strategy.parameters).map(([k, spec]) => [k, spec.default]),
  )
}

/** Parameter values that differ from the strategy defaults are worth flagging in results. */
export function parametersEqual(a: Parameters, b: Parameters): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)])
  for (const key of keys) if (a[key] !== b[key]) return false
  return true
}

/** Mirrors optimization._is_valid_parameter_combination so problems show before the API's 422. */
export function parameterIssues(strategy: string, p: Parameters): string[] {
  const issues: string[] = []
  const notBelow = (a: string, b: string) => isNum(p[a]) && isNum(p[b]) && p[a] >= p[b]
  if (
    ['moving_average', 'ema', 'macd'].includes(strategy) &&
    notBelow('fast_window', 'slow_window')
  )
    issues.push('The fast window must be shorter than the slow window.')
  if (
    ['rsi', 'stochastic', 'cci'].includes(strategy) &&
    notBelow('entry_threshold', 'exit_threshold')
  )
    issues.push('The entry threshold must be below the exit threshold.')
  if (strategy === 'donchian' && notBelow('exit_window', 'entry_window'))
    issues.push('The exit window must be shorter than the entry window.')
  return issues
}
