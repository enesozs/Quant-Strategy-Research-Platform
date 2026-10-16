// Default per-page form state for the strategy pages, shared with the Strategy Guide's
// "Backtest it / Optimize / Validate" shortcuts.

import type { Objective, OptimizeMode, Parameters } from '@/api/types'
import { setStoreValue } from './store'

export interface BacktestForm {
  strategy: string
  /** Parameter values remembered per strategy. */
  parameters: Record<string, Parameters>
}

export interface OptimizeForm {
  strategy: string
  objective: Objective
  mode: OptimizeMode
  /** Custom grid text per strategy and parameter ("5, 10, 20"). */
  custom: Record<string, Record<string, string>>
  refinement_points: number
}

export interface ValidateForm {
  strategy: string
  objective: Objective
  split_date: string
  window_type: 'expanding' | 'rolling'
  initial_training_years: number
  test_window_years: number
}

export const DEFAULT_BACKTEST_FORM: BacktestForm = { strategy: 'moving_average', parameters: {} }

export const DEFAULT_OPTIMIZE_FORM: OptimizeForm = {
  strategy: 'moving_average',
  objective: 'sharpe_ratio',
  mode: 'predefined',
  custom: {},
  refinement_points: 5,
}

export const DEFAULT_VALIDATE_FORM: ValidateForm = {
  strategy: 'moving_average',
  objective: 'sharpe_ratio',
  split_date: '2024-01-01',
  window_type: 'expanding',
  initial_training_years: 2,
  test_window_years: 1,
}

const FORMS = {
  'backtest:form': DEFAULT_BACKTEST_FORM,
  'optimize:form': DEFAULT_OPTIMIZE_FORM,
  'validate:form': DEFAULT_VALIDATE_FORM,
} as const

/** Preselect a strategy on a page, keeping any other settings the user already made there. */
export function selectStrategy(key: keyof typeof FORMS, strategy: string) {
  setStoreValue<{ strategy: string }>(key, (previous) => ({
    ...FORMS[key],
    ...previous,
    strategy,
  }))
}
