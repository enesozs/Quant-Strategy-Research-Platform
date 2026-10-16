// Default form values (match the Streamlit app and the API contract defaults).

import type { MarketRequest, PairsAssumptions } from '@/api/types'

export type MarketForm = Required<MarketRequest>

export const DEFAULT_MARKET: MarketForm = {
  ticker: 'AAPL',
  start_date: '2020-01-01',
  end_date: '2026-01-01',
  initial_capital: 10_000,
  transaction_cost_bps: 10,
  risk_free_rate: 0,
  cash_earns_risk_free: true,
}

export type PairsAssumptionsForm = Required<PairsAssumptions>

export const DEFAULT_PAIRS_ASSUMPTIONS: PairsAssumptionsForm = {
  start_date: '2020-01-01',
  end_date: '2026-01-01',
  initial_capital: 10_000,
  transaction_cost_bps: 10,
  risk_free_rate: 0,
  cash_earns_risk_free: true,
  borrow_fee: 0,
}

/** Normalize a ticker the way the Streamlit app did (upper-case, trimmed). */
export function cleanTicker(value: string): string {
  return value.trim().toUpperCase()
}

export function dateIssues(start: string, end: string): string[] {
  if (!start || !end) return ['Choose a start and end date.']
  return start < end ? [] : ['Start date must be before end date.']
}

export interface AssumptionValues {
  ticker?: string
  start_date: string
  end_date: string
  initial_capital: number
  transaction_cost_bps: number
  risk_free_rate: number
  cash_earns_risk_free: boolean
  borrow_fee?: number
}

export function marketIssues(value: AssumptionValues): string[] {
  const issues: string[] = []
  if (value.ticker !== undefined && !value.ticker.trim()) issues.push('Enter a ticker.')
  if (!(value.start_date < value.end_date)) issues.push('Start date must be before end date.')
  return issues
}
