// Pairs builder arguments exposed in the UI, per method (defaults mirror the Python builders).
// The API validates names against each builder's signature, so only the selected method's
// parameters are sent.

import type { PairsMethod, PairsParams } from '@/api/types'

export interface PairsParamSpec {
  key: string
  label: string
  kind: 'int' | 'float' | 'bool'
  default: number | boolean
  min?: number
  max?: number
  step?: number
  /** Show and edit as a percentage of a decimal value. */
  percent?: boolean
  hint?: string
}

export interface PairsParamGroup {
  title: string
  params: PairsParamSpec[]
}

const WALK_FORWARD: PairsParamGroup = {
  title: 'Walk-forward design',
  params: [
    {
      key: 'formation_years',
      label: 'Formation (years)',
      kind: 'int',
      default: 2,
      min: 1,
      max: 10,
      step: 1,
    },
    {
      key: 'trading_months',
      label: 'Trading (months)',
      kind: 'int',
      default: 6,
      min: 1,
      max: 24,
      step: 1,
    },
  ],
}

export const TRADING_RULES: PairsParamGroup = {
  title: 'Trading rules',
  params: [
    {
      key: 'entry_zscore',
      label: 'Entry z-score',
      kind: 'float',
      default: 2,
      min: 0.5,
      max: 5,
      step: 0.25,
    },
    {
      key: 'exit_zscore',
      label: 'Exit z-score',
      kind: 'float',
      // Exit on full convergence (the classic Gatev rule). Holding to zero captures more of each
      // reversion against the same round-trip cost; it beat 0.5 for all three methods on both
      // 2012-2018 and 2019-2025 across ten pairs.
      default: 0,
      min: 0,
      max: 4.5,
      step: 0.25,
    },
    {
      key: 'stop_zscore',
      label: 'Stop z-score',
      kind: 'float',
      default: 4,
      min: 1,
      max: 10,
      step: 0.25,
    },
    {
      key: 'maximum_holding_days',
      label: 'Max holding (days)',
      kind: 'int',
      default: 60,
      min: 1,
      max: 504,
      step: 5,
    },
  ],
}

export const METHOD_GROUPS: Record<PairsMethod, PairsParamGroup[]> = {
  distance: [
    WALK_FORWARD,
    {
      title: 'Relationship-break filter',
      params: [
        {
          key: 'relationship_break_window',
          label: 'Stability window (days)',
          kind: 'int',
          default: 20,
          min: 5,
          max: 120,
          step: 5,
        },
        {
          key: 'maximum_recent_volatility_ratio',
          label: 'Max recent/formation vol',
          kind: 'float',
          default: 2,
          min: 1,
          max: 10,
          step: 0.25,
        },
        {
          key: 'maximum_recent_mean_shift_z',
          label: 'Max mean shift (σ)',
          kind: 'float',
          default: 2.5,
          min: 0.5,
          max: 10,
          step: 0.25,
        },
        {
          key: 'minimum_recent_return_correlation',
          label: 'Min recent correlation',
          kind: 'float',
          default: 0,
          min: -1,
          max: 1,
          step: 0.05,
        },
      ],
    },
  ],
  cointegration: [
    WALK_FORWARD,
    {
      title: 'Cointegration qualification',
      params: [
        {
          key: 'require_qualification',
          label: 'Trade only qualified windows',
          kind: 'bool',
          default: true,
          hint: 'Off = diagnostic mode: every window trades a plain OLS z-score.',
        },
        {
          key: 'maximum_cointegration_pvalue',
          label: 'Max coint. p-value',
          kind: 'float',
          default: 0.1,
          min: 0.01,
          max: 0.5,
          step: 0.01,
        },
        {
          key: 'adf_reference_pvalue',
          label: 'ADF reference p',
          kind: 'float',
          default: 0.1,
          min: 0.01,
          max: 0.5,
          step: 0.01,
        },
        {
          key: 'minimum_half_life_days',
          label: 'Min half-life (days)',
          kind: 'float',
          default: 2,
          min: 0.5,
          max: 100,
          step: 0.5,
        },
        {
          key: 'maximum_half_life_days',
          label: 'Max half-life (days)',
          kind: 'float',
          default: 120,
          min: 1,
          max: 500,
          step: 5,
        },
        {
          key: 'minimum_mean_crossings',
          label: 'Min mean crossings',
          kind: 'int',
          default: 4,
          min: 0,
          max: 100,
          step: 1,
        },
      ],
    },
  ],
  kalman: [
    {
      title: 'Kalman filter',
      params: [
        {
          key: 'warmup_window',
          label: 'Warm-up (days)',
          kind: 'int',
          default: 120,
          min: 20,
          max: 504,
          step: 10,
        },
        {
          key: 'zscore_window',
          label: 'Z-score window (days)',
          kind: 'int',
          default: 60,
          min: 10,
          max: 252,
          step: 5,
        },
        {
          key: 'state_noise',
          label: 'State noise',
          kind: 'float',
          default: 0.00001,
          min: 0.000001,
          max: 0.01,
          step: 0.00001,
          hint: 'Higher lets α and β adapt faster.',
        },
        {
          key: 'observation_noise_scale',
          label: 'Observation noise scale',
          kind: 'float',
          default: 1,
          min: 0.1,
          max: 10,
          step: 0.1,
        },
        {
          key: 'minimum_hedge_ratio',
          label: 'Min hedge ratio',
          kind: 'float',
          default: 0.25,
          min: 0.01,
          max: 2,
          step: 0.05,
        },
        {
          key: 'maximum_hedge_ratio',
          label: 'Max hedge ratio',
          kind: 'float',
          default: 4,
          min: 0.1,
          max: 10,
          step: 0.25,
        },
      ],
    },
  ],
}

export function methodGroups(method: PairsMethod): PairsParamGroup[] {
  return [...METHOD_GROUPS[method], TRADING_RULES]
}

export function defaultParams(method: PairsMethod): PairsParams {
  return Object.fromEntries(
    methodGroups(method).flatMap((g) => g.params.map((p) => [p.key, p.default])),
  )
}

/** Current params for a method: stored overrides on top of defaults, restricted to known keys. */
export function resolveParams(method: PairsMethod, stored: PairsParams | undefined): PairsParams {
  const defaults = defaultParams(method)
  const result: PairsParams = { ...defaults }
  for (const key of Object.keys(defaults)) if (stored && key in stored) result[key] = stored[key]
  return result
}

export function paramIssues(params: PairsParams): string[] {
  const issues: string[] = []
  const n = (key: string) => (typeof params[key] === 'number' ? (params[key] as number) : null)
  const entry = n('entry_zscore')
  const exit = n('exit_zscore')
  const stop = n('stop_zscore')
  if (entry !== null && exit !== null && exit >= entry)
    issues.push('Exit z-score must be below the entry z-score.')
  if (entry !== null && stop !== null && stop <= entry)
    issues.push('Stop z-score must be above the entry z-score.')
  const lo = n('minimum_half_life_days')
  const hi = n('maximum_half_life_days')
  if (lo !== null && hi !== null && lo >= hi)
    issues.push('Minimum half-life must be below the maximum.')
  const hlo = n('minimum_hedge_ratio')
  const hhi = n('maximum_hedge_ratio')
  if (hlo !== null && hhi !== null && hlo >= hhi)
    issues.push('Minimum hedge ratio must be below the maximum.')
  return issues
}

/** Params for the universe endpoints: formation_years is a body field there. */
export function universeParams(params: PairsParams): PairsParams {
  const rest = { ...params }
  delete rest.formation_years
  return rest
}

/** Current params of the selected method in a pairs form. */
export function currentParams(form: {
  method: PairsMethod
  params: Partial<Record<PairsMethod, PairsParams>>
}): PairsParams {
  return resolveParams(form.method, form.params[form.method])
}
