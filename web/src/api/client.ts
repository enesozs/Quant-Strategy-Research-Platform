// Typed client for the FastAPI backend (see api/CONTRACT.md). One fetcher, one query-options
// factory and one hook per endpoint. Research endpoints are POSTs that can take tens of seconds,
// so they run on demand (useResearchRun) and are cached by request body.

import { queryOptions, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { stableStringify } from '@/lib/equal'
import { getStoreValue, setStoreValue, usePageState } from '@/state/store'
import type {
  BacktestRequest,
  BacktestResponse,
  CompareRequest,
  CompareResponse,
  Health,
  Meta,
  OptimizeRequest,
  OptimizeResponse,
  PairsDiscoverResponse,
  PairsPortfolioResponse,
  PairsResearchRequest,
  PairsResearchResponse,
  PairsSensitivityResponse,
  PairsUniverseRequest,
  SplitRequest,
  SplitResponse,
  WalkForwardRequest,
  WalkForwardResponse,
} from './types'

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the research API. Is the backend running on port 8020?')
  }
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`.trim()
    try {
      const payload: unknown = await response.json()
      if (payload && typeof payload === 'object' && 'detail' in payload) {
        const value = (payload as { detail: unknown }).detail
        if (typeof value === 'string') detail = value
        // FastAPI's own validation errors arrive as a list of {loc, msg}.
        else if (Array.isArray(value))
          detail = value
            .map((item: { loc?: unknown[]; msg?: string }) =>
              [item.loc?.slice(1).join('.'), item.msg].filter(Boolean).join(': '),
            )
            .join('; ')
      }
    } catch {
      // Non-JSON error page (e.g. proxy error): keep the status line.
    }
    throw new ApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/health'),
  meta: () => request<Meta>('/meta'),
  backtest: (body: BacktestRequest) => request<BacktestResponse>('/backtest', body),
  compare: (body: CompareRequest) => request<CompareResponse>('/compare', body),
  optimize: (body: OptimizeRequest) => request<OptimizeResponse>('/optimize', body),
  validateSplit: (body: SplitRequest) => request<SplitResponse>('/validate/split', body),
  validateWalkForward: (body: WalkForwardRequest) =>
    request<WalkForwardResponse>('/validate/walk-forward', body),
  pairsResearch: (body: PairsResearchRequest) =>
    request<PairsResearchResponse>('/pairs/research', body),
  pairsSensitivity: (body: PairsResearchRequest) =>
    request<PairsSensitivityResponse>('/pairs/sensitivity', body),
  pairsDiscover: (body: PairsUniverseRequest) =>
    request<PairsDiscoverResponse>('/pairs/discover', body),
  pairsPortfolio: (body: PairsUniverseRequest) =>
    request<PairsPortfolioResponse>('/pairs/portfolio', body),
}

// ---------------------------------------------------------------------------------------------
// Query options

const MINUTE = 60_000

/** Research results are deterministic for a request body (market data aside), so an identical
 * re-run within a few minutes is served from cache. */
interface ResearchQuery<Res> {
  queryKey: readonly [string, string]
  queryFn: () => Promise<Res>
  staleTime: number
  gcTime: number
  retry: false
}

function research<Req, Res>(name: string, fetcher: (body: Req) => Promise<Res>) {
  return (body: Req): ResearchQuery<Res> => ({
    queryKey: [name, stableStringify(body)],
    queryFn: () => fetcher(body),
    staleTime: 5 * MINUTE,
    gcTime: 60 * MINUTE,
    retry: false,
  })
}

export const queries = {
  meta: () =>
    queryOptions({ queryKey: ['meta'], queryFn: api.meta, staleTime: Infinity, retry: 1 }),
  backtest: research('backtest', api.backtest),
  compare: research('compare', api.compare),
  optimize: research('optimize', api.optimize),
  validateSplit: research('validate-split', api.validateSplit),
  validateWalkForward: research('validate-walk-forward', api.validateWalkForward),
  pairsResearch: research('pairs-research', api.pairsResearch),
  pairsSensitivity: research('pairs-sensitivity', api.pairsSensitivity),
  pairsDiscover: research('pairs-discover', api.pairsDiscover),
  pairsPortfolio: research('pairs-portfolio', api.pairsPortfolio),
}

export const useMeta = () => useQuery(queries.meta())

// ---------------------------------------------------------------------------------------------
// On-demand research runs

export interface RunState<Req, Res> {
  /** Request of the result currently shown (the last successful run). */
  request: Req | null
  data: Res | null
  /** Request currently in flight. */
  pending: Req | null
  error: string | null
  /** Wall-clock start of the in-flight request, for the elapsed timer. */
  startedAt: number | null
}

const EMPTY: RunState<never, never> = {
  request: null,
  data: null,
  pending: null,
  error: null,
  startedAt: null,
}

/**
 * Runs a research endpoint on demand and keeps the outcome in the page store, so the last
 * result survives navigation and stays visible while a new run is in flight. A request that
 * finishes after the user navigated away still lands in the store.
 */
export function useResearchRun<Req, Res>(key: string, options: (body: Req) => ResearchQuery<Res>) {
  const client = useQueryClient()
  const [state] = usePageState<RunState<Req, Res>>(`run:${key}`, EMPTY)

  const run = useCallback(
    async (body: Req) => {
      const storeKey = `run:${key}`
      const current = getStoreValue<RunState<Req, Res>>(storeKey, EMPTY)
      if (current.pending) return
      setStoreValue<RunState<Req, Res>>(storeKey, (previous) => ({
        ...previous,
        pending: body,
        error: null,
        startedAt: Date.now(),
      }))
      try {
        const data = await client.fetchQuery(options(body))
        setStoreValue<RunState<Req, Res>>(storeKey, {
          request: body,
          data,
          pending: null,
          error: null,
          startedAt: null,
        })
      } catch (error) {
        setStoreValue<RunState<Req, Res>>(storeKey, (previous) => ({
          ...previous,
          pending: null,
          startedAt: null,
          error: error instanceof Error ? error.message : String(error),
        }))
      }
    },
    [client, key, options],
  )

  return { ...state, running: state.pending !== null, run }
}

export const useBacktestRun = () => useResearchRun('backtest', queries.backtest)
export const useCompareRun = () => useResearchRun('compare', queries.compare)
export const useOptimizeRun = () => useResearchRun('optimize', queries.optimize)
export const useSplitRun = () => useResearchRun('validate-split', queries.validateSplit)
export const useWalkForwardRun = () =>
  useResearchRun('validate-walk-forward', queries.validateWalkForward)
export const usePairsResearchRun = () => useResearchRun('pairs-research', queries.pairsResearch)
export const usePairsSensitivityRun = () =>
  useResearchRun('pairs-sensitivity', queries.pairsSensitivity)
export const usePairsDiscoverRun = () => useResearchRun('pairs-discover', queries.pairsDiscover)
export const usePairsPortfolioRun = () => useResearchRun('pairs-portfolio', queries.pairsPortfolio)
