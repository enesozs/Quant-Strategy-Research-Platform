// Single-asset assumptions are shared by Compare, Backtest, Optimize and Validate, so the ticker
// and dates follow the user between pages. Pairs pages share their own assumptions.

import {
  DEFAULT_MARKET,
  DEFAULT_PAIRS_ASSUMPTIONS,
  type MarketForm,
  type PairsAssumptionsForm,
} from './defaults'
import { usePageState } from './store'

export function useMarket() {
  return usePageState<MarketForm>('market', DEFAULT_MARKET)
}

export function usePairsAssumptions() {
  return usePageState<PairsAssumptionsForm>('pairs:assumptions', DEFAULT_PAIRS_ASSUMPTIONS)
}
