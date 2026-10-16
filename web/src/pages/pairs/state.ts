import type { PairsMethod, PairsParams } from '@/api/types'
import { usePageState } from '@/state/store'

export interface PairsForm {
  method: PairsMethod
  ticker_a: string
  ticker_b: string
  /** Parameter values remembered per method. */
  params: Partial<Record<PairsMethod, PairsParams>>
}

export function usePairsForm() {
  return usePageState<PairsForm>('pairs:form', {
    method: 'distance',
    ticker_a: 'KO',
    ticker_b: 'PEP',
    params: {},
  })
}

export interface UniverseForm {
  preset: string
  tickers: string
  formation_years: number
  discover_top_n: number
  portfolio_top_n: number
}

export function useUniverseForm() {
  return usePageState<UniverseForm>('pairs:universe', {
    preset: 'Beverages & snacks',
    tickers: 'KO, PEP, KDP, MNST, MDLZ, GIS, HSY',
    formation_years: 2,
    discover_top_n: 10,
    portfolio_top_n: 5,
  })
}

export function parseTickers(text: string): string[] {
  return [
    ...new Set(
      text
        .split(/[\s,;]+/)
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean),
    ),
  ]
}

export function universeIssues(universe: UniverseForm): string[] {
  return parseTickers(universe.tickers).length < 2 ? ['Enter at least two tickers.'] : []
}
