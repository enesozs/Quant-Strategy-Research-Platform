import { useMemo } from 'react'
import { usePairsResearchRun, usePairsSensitivityRun } from '@/api/client'
import type {
  Meta,
  PairsParams,
  PairsResearchRequest,
  PairsResearchResponse,
  PairsSensitivityResponse,
} from '@/api/types'
import { EChart } from '@/charts/EChart'
import { timeLines } from '@/charts/lines'
import { zscoreChart } from '@/charts/zscore'
import {
  ControlPanel,
  EmptyState,
  FieldGroup,
  ResearchLayout,
  ResultsArea,
  Spinner,
} from '@/components/controls/ControlPanel'
import { MarketFields } from '@/components/controls/MarketFields'
import { WithMeta } from '@/components/controls/StrategyFields'
import { Alert } from '@/components/ui/Alert'
import { Badge, InSampleBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Panel } from '@/components/ui/Card'
import { DataTable } from '@/components/ui/DataTable'
import { TextInput } from '@/components/ui/Field'
import { MetricTile, MetricTiles, TileGrid } from '@/components/ui/MetricTile'
import { sameRequest } from '@/lib/equal'
import {
  formatCurrency,
  formatDateRange,
  formatInteger,
  formatNumber,
  formatPercent,
  formatRatio,
  humanize,
  isNum,
  formatPercentTick,
} from '@/lib/format'
import { hasColumn } from '@/lib/series'
import { cleanTicker, marketIssues } from '@/state/defaults'
import { usePairsAssumptions } from '@/state/market'
import { useChartColors } from '@/theme/chart'
import { MethodField, MethodParamFields } from './PairsControls'
import { methodGroups, paramIssues, currentParams } from './params'
import { usePairsForm } from './state'

export default function ResearchPage() {
  return <WithMeta>{(meta) => <Research meta={meta} />}</WithMeta>
}

function Research({ meta }: { meta: Meta }) {
  const [assumptions, setAssumptions] = usePairsAssumptions()
  const [form, setForm] = usePairsForm()
  const research = usePairsResearchRun()
  const sensitivity = usePairsSensitivityRun()
  const params = currentParams(form)

  const request: PairsResearchRequest = {
    ...assumptions,
    method: form.method,
    ticker_a: cleanTicker(form.ticker_a),
    ticker_b: cleanTicker(form.ticker_b),
    params,
  }
  const issues = [...marketIssues(assumptions), ...paramIssues(params)]
  if (!request.ticker_a || !request.ticker_b) issues.push('Enter both tickers.')
  else if (request.ticker_a === request.ticker_b) issues.push('Choose two different tickers.')
  const stale = research.request !== null && !sameRequest(request, research.request)
  const submit = () => research.run(request)
  const busy = research.running || sensitivity.running

  return (
    <ResearchLayout
      panel={
        <ControlPanel
          onRun={submit}
          running={research.running}
          issues={issues}
          runLabel="Run pairs research"
          secondary={
            <Button
              className="w-full"
              disabled={busy || issues.length > 0}
              onClick={() => sensitivity.run(request)}
            >
              {sensitivity.running && <Spinner />}
              {sensitivity.running ? 'Running sensitivity…' : 'Run parameter sensitivity'}
            </Button>
          }
        >
          <FieldGroup title="Pair">
            <div className="grid grid-cols-2 gap-3">
              <TextInput
                label="Asset A"
                value={form.ticker_a}
                onChange={(ticker_a) => setForm((f) => ({ ...f, ticker_a }))}
                uppercase
                mono
              />
              <TextInput
                label="Asset B"
                value={form.ticker_b}
                onChange={(ticker_b) => setForm((f) => ({ ...f, ticker_b }))}
                uppercase
                mono
              />
            </div>
            <MethodField meta={meta} form={form} setForm={setForm} />
          </FieldGroup>
          <MethodParamFields form={form} setForm={setForm} />
          <MarketFields value={assumptions} onChange={setAssumptions} showTicker={false} />
        </ControlPanel>
      }
    >
      <ResultsArea
        hasData={research.data !== null}
        running={research.running}
        startedAt={research.startedAt}
        error={research.error}
        stale={stale}
        onRerun={submit}
        runningText="Downloading both legs and walking the spread model forward…"
        empty={
          <EmptyState title="Research a pair">
            Pick two related assets and a spread model. Positions open on the day after a signal;
            both legs pay costs and the short leg pays the borrow fee.
          </EmptyState>
        }
      >
        {research.data && research.request && (
          <ResearchResults data={research.data} request={research.request} />
        )}
      </ResultsArea>

      <SensitivitySection
        data={sensitivity.data}
        request={sensitivity.request}
        running={sensitivity.running}
        error={sensitivity.error}
        stale={sensitivity.request !== null && !sameRequest(request, sensitivity.request)}
        onApply={(recommended) =>
          setForm((f) => ({
            ...f,
            params: { ...f.params, [f.method]: { ...currentParams(f), ...recommended } },
          }))
        }
        currentMethod={form.method}
      />
    </ResearchLayout>
  )
}

function ResearchResults({
  data,
  request,
}: {
  data: PairsResearchResponse
  request: PairsResearchRequest
}) {
  const c = useChartColors()
  const { series } = data
  const params = request.params ?? {}
  const entry = Number(params.entry_zscore ?? 2)
  const exit = Number(params.exit_zscore ?? 0)
  const stop = Number(params.stop_zscore ?? 4)
  const pairLabel = `${data.ticker_a} / ${data.ticker_b}`

  const zOption = useMemo(
    () =>
      zscoreChart(c, {
        dates: series.dates,
        z: series.columns.spread_zscore ?? [],
        position: series.columns.pair_position,
        trades: data.trades,
        bands: { entry, exit, stop },
      }),
    [c, data, series, entry, exit, stop],
  )
  const pricesOption = useMemo(
    () =>
      timeLines(c, {
        dates: series.dates,
        lines: [
          { name: data.ticker_a, values: series.columns.normalized_a, color: c.series[0] },
          { name: data.ticker_b, values: series.columns.normalized_b, color: c.series[1] },
        ],
        format: (v) => formatNumber(v, 3),
        axisFormat: (v) => formatNumber(v, 2),
        reference: { value: 1 },
      }),
    [c, data, series],
  )
  const betaOption = useMemo(() => {
    const betaKeys = ['dynamic_beta', 'hedge_beta'].filter((key) => hasColumn(series, key))
    return betaKeys.length
      ? timeLines(c, {
          dates: series.dates,
          lines: betaKeys.map((key, i) => ({
            name: key === 'dynamic_beta' ? 'Filtered β' : 'Hedge β in use',
            values: series.columns[key],
            color: i === 0 ? c.series[0] : c.series[1],
            step: key === 'hedge_beta',
          })),
          format: (v) => formatNumber(v, 3),
          axisFormat: (v) => formatNumber(v, 2),
        })
      : null
  }, [c, series])
  const equityOption = useMemo(
    () =>
      timeLines(c, {
        dates: series.dates,
        lines: [
          { name: 'Pair strategy', values: series.columns.strategy_equity, color: c.series[0] },
          { name: '50/50 long both', values: series.columns.benchmark_equity, color: c.reference },
        ],
        format: (v) => formatCurrency(v),
        axisFormat: (v) => formatCurrency(v, { compact: true }),
        reference: { value: request.initial_capital ?? 10_000 },
      }),
    [c, series, request.initial_capital],
  )
  const drawdownOption = useMemo(
    () =>
      timeLines(c, {
        dates: series.dates,
        lines: [
          {
            name: 'Pair strategy',
            values: series.columns.strategy_drawdown,
            color: c.series[0],
            area: true,
          },
          ...(hasColumn(series, 'benchmark_drawdown')
            ? [
                {
                  name: '50/50 long both',
                  values: series.columns.benchmark_drawdown,
                  color: c.reference,
                },
              ]
            : []),
        ],
        format: (v) => formatPercent(v),
        axisFormat: formatPercentTick,
        maxZero: true,
      }),
    [c, series],
  )

  const exits = Object.entries(data.exit_reasons).sort((a, b) => b[1] - a[1])
  const totalExits = exits.reduce((sum, [, n]) => sum + n, 0)
  const wins = data.trades.filter((t) => isNum(t.net_pair_return) && t.net_pair_return > 0).length

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <span className="font-mono font-semibold text-ink">{pairLabel}</span>
        <Badge>{humanize(data.method)}</Badge>
        <span>{formatDateRange(request.start_date, request.end_date)}</span>
      </div>

      <MetricTiles
        metrics={data.metrics}
        reference={data.benchmark_metrics}
        referenceLabel="vs 50/50"
      />
      <TileGrid className="sm:grid-cols-4 2xl:grid-cols-4">
        <MetricTile
          label="Trades"
          value={formatInteger(data.trades.length)}
          hint={data.trades.length ? `${wins} profitable` : 'no trades'}
        />
        <MetricTile
          label="Return correlation"
          value={formatRatio(data.return_correlation)}
          hint="daily returns"
        />
        <MetricTile
          label="Price correlation"
          value={formatRatio(data.price_correlation)}
          hint="levels; often spurious"
        />
        <MetricTile
          label="Final value"
          value={formatCurrency(data.metrics.final_value)}
          hint="strategy"
        />
      </TileGrid>

      <Panel
        title="Spread z-score"
        description="Entries when |z| crosses the entry band, exits back inside the exit band, stops beyond the stop band. Shaded periods hold the pair."
      >
        <EChart
          option={zOption}
          height={320}
          ariaLabel="Spread z-score with entry, exit and stop bands and trade markers"
        />
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Normalized prices" description="Both legs rebased to 1 at the start.">
          <EChart
            option={pricesOption}
            height={260}
            ariaLabel={`Normalized prices of ${pairLabel}`}
          />
        </Panel>
        <Panel
          title="Portfolio value"
          description="Pair strategy against a 50/50 long-only holding of both legs."
        >
          <EChart
            option={equityOption}
            height={260}
            ariaLabel="Pair strategy equity against the 50/50 benchmark"
          />
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Drawdown" description="Decline from the running peak.">
          <EChart option={drawdownOption} height={220} ariaLabel="Pair strategy drawdown" />
        </Panel>
        {betaOption ? (
          <Panel
            title="Hedge ratio"
            description="Units of B per unit of A. The step line is the ratio locked in for each trade or window."
          >
            <EChart option={betaOption} height={220} ariaLabel="Hedge ratio over time" />
          </Panel>
        ) : (
          <Panel title="Exit reasons" description="Why each trade closed.">
            <ExitReasons exits={exits} total={totalExits} />
          </Panel>
        )}
      </div>

      {betaOption && (
        <Panel title="Exit reasons" description="Why each trade closed.">
          <ExitReasons exits={exits} total={totalExits} />
        </Panel>
      )}

      <Panel
        title="Trades"
        description="One row per round trip; returns are on the pair's capital, net of both legs' costs."
      >
        <DataTable
          caption="Trade log"
          rows={data.trades}
          rowTone={(row) =>
            isNum(row.net_pair_return) && row.net_pair_return < 0 ? 'worst' : undefined
          }
          emptyText="No trades in this sample — the spread never crossed the entry band under these rules."
        />
      </Panel>

      <Panel
        title="Diagnostics"
        description="Per-window statistics from the formation and trading windows."
      >
        <DataTable caption="Pairs diagnostics" rows={data.diagnostics} />
      </Panel>
    </>
  )
}

function ExitReasons({ exits, total }: { exits: Array<[string, number]>; total: number }) {
  if (!exits.length) return <p className="py-4 text-sm text-muted">No closed trades.</p>
  return (
    <ul className="space-y-2.5">
      {exits.map(([reason, count]) => (
        <li
          key={reason}
          className="grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-3 text-[13px]"
        >
          <span className="truncate text-ink-2">{humanize(reason)}</span>
          <span className="h-2 overflow-hidden rounded-full bg-surface-2">
            <span
              className="block h-full rounded-full bg-accent"
              style={{ width: `${(count / total) * 100}%` }}
            />
          </span>
          <span className="num font-mono text-xs text-ink">{count}</span>
        </li>
      ))}
    </ul>
  )
}

function SensitivitySection({
  data,
  request,
  running,
  error,
  stale,
  onApply,
  currentMethod,
}: {
  data: PairsSensitivityResponse | null
  request: PairsResearchRequest | null
  running: boolean
  error: string | null
  stale: boolean
  onApply: (params: PairsParams) => void
  currentMethod: string
}) {
  if (!data && !running && !error) return null
  const labels = new Map(
    request
      ? methodGroups(request.method).flatMap((g) => g.params.map((p) => [p.key, p.label] as const))
      : [],
  )
  return (
    <div className="mt-4 space-y-3">
      {running && (
        <Alert tone="info" title="Running parameter sensitivity">
          Varying one parameter at a time around the current settings, then combining the winners.
        </Alert>
      )}
      {error && !running && (
        <Alert tone="error" title="Sensitivity failed">
          {error}
        </Alert>
      )}
      {data && request && (
        <Panel
          title="Parameter sensitivity"
          description="One-at-a-time variations around the current settings, then the combined winners. Chosen on the same sample it reports — validate before trusting it."
          actions={
            <>
              <InSampleBadge />
              {stale && <Badge>Settings changed</Badge>}
            </>
          }
        >
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface-2 px-3 py-2.5">
            <div className="min-w-0 text-xs">
              <p className="font-medium text-ink-2">Recommended {request.method} parameters</p>
              <p className="num mt-1 font-mono text-ink">
                {Object.entries(data.recommended_params)
                  .filter(([k]) => labels.has(k))
                  .map(([k, v]) => `${labels.get(k) ?? humanize(k)} ${String(v)}`)
                  .join(' · ')}
              </p>
            </div>
            <Button
              size="sm"
              variant="primary"
              disabled={request.method !== currentMethod}
              onClick={() =>
                onApply(
                  Object.fromEntries(
                    Object.entries(data.recommended_params).filter(
                      ([k, v]) =>
                        labels.has(k) && (typeof v === 'number' || typeof v === 'boolean'),
                    ),
                  ),
                )
              }
            >
              Apply to controls
            </Button>
          </div>
          <DataTable
            caption="Pairs parameter sensitivity"
            rows={data.rows}
            rowTone={(row) => (row.selected === true ? 'best' : undefined)}
          />
        </Panel>
      )}
    </div>
  )
}
