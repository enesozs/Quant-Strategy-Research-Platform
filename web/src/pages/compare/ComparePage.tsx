import clsx from 'clsx'
import { useMemo } from 'react'
import { useCompareRun } from '@/api/client'
import type { CompareRequest, CompareResponse, Meta, Objective, Row } from '@/api/types'
import { EChart } from '@/charts/EChart'
import { drawdownBars, riskReturnChart, type StrategyPoint } from '@/charts/compare'
import { timeLines } from '@/charts/lines'
import {
  ControlPanel,
  EmptyState,
  FieldGroup,
  ResearchLayout,
  ResultsArea,
} from '@/components/controls/ControlPanel'
import { MarketFields } from '@/components/controls/MarketFields'
import { ObjectiveSelect, WithMeta } from '@/components/controls/StrategyFields'
import { PageBody, PageHeader } from '@/components/shell/PageHeader'
import { Badge, InSampleBadge } from '@/components/ui/Badge'
import { Panel } from '@/components/ui/Card'
import { DataTable, type Column } from '@/components/ui/DataTable'
import { Switch } from '@/components/ui/Field'
import { MetricTile, TileGrid } from '@/components/ui/MetricTile'
import { Alert } from '@/components/ui/Alert'
import { sameRequest } from '@/lib/equal'
import {
  formatCurrency,
  formatDateRange,
  formatMetric,
  formatPercent,
  formatRatio,
  isNum,
  formatPercentTick,
} from '@/lib/format'
import { drawdown } from '@/lib/series'
import { cleanTicker, marketIssues } from '@/state/defaults'
import { useMarket } from '@/state/market'
import { usePageState } from '@/state/store'
import { useChartColors } from '@/theme/chart'
import { findObjective } from '@/lib/meta'

interface CompareForm {
  use_optimized_parameters: boolean
  objective: Objective
}

const BENCHMARK_KEYS = new Set(['buy_and_hold', 'buy_hold'])
const MAX_PICKED = 4

export default function ComparePage() {
  return (
    <>
      <PageHeader
        title="Compare strategies"
        description="Run every registered strategy on the same ticker, period, capital and cost assumptions, and rank them on return, risk-adjusted return, volatility and drawdown."
      />
      <PageBody>
        <WithMeta>{(meta) => <Compare meta={meta} />}</WithMeta>
      </PageBody>
    </>
  )
}

function Compare({ meta }: { meta: Meta }) {
  const [market, setMarket] = useMarket()
  const [form, setForm] = usePageState<CompareForm>('compare:form', {
    use_optimized_parameters: false,
    objective: 'sharpe_ratio',
  })
  const run = useCompareRun()

  const request: CompareRequest = {
    ...market,
    ticker: cleanTicker(market.ticker),
    use_optimized_parameters: form.use_optimized_parameters,
    objective: form.use_optimized_parameters ? form.objective : undefined,
  }
  const issues = marketIssues(market)
  const stale = run.request !== null && !sameRequest(request, run.request)
  const submit = () => run.run(request)

  return (
    <ResearchLayout
      panel={
        <ControlPanel
          onRun={submit}
          running={run.running}
          issues={issues}
          runLabel="Compare all strategies"
        >
          <MarketFields value={market} onChange={setMarket} />
          <FieldGroup title="Parameters">
            <Switch
              label="Use optimized parameters"
              checked={form.use_optimized_parameters}
              onChange={(use_optimized_parameters) =>
                setForm({ ...form, use_optimized_parameters })
              }
              hint="Searches each strategy's predefined grid on this same sample first. Results become in-sample and much slower to compute."
            />
            {form.use_optimized_parameters && (
              <ObjectiveSelect
                meta={meta}
                value={form.objective}
                onChange={(objective) => setForm({ ...form, objective })}
                label="Optimization objective"
              />
            )}
          </FieldGroup>
        </ControlPanel>
      }
    >
      <ResultsArea
        hasData={run.data !== null}
        running={run.running}
        startedAt={run.startedAt}
        error={run.error}
        stale={stale}
        onRerun={submit}
        runningText={
          request.use_optimized_parameters
            ? 'Optimizing and backtesting every strategy — this can take a minute.'
            : 'Backtesting every strategy on the same sample…'
        }
        empty={
          <EmptyState title="Compare every strategy on one sample">
            Pick a ticker and period, then run the comparison. Results rank 15 strategies and Buy
            and Hold under identical assumptions.
          </EmptyState>
        }
      >
        {run.data && run.request && (
          <CompareResults data={run.data} request={run.request} meta={meta} />
        )}
      </ResultsArea>
    </ResearchLayout>
  )
}

function isBenchmark(row: Row): boolean {
  return BENCHMARK_KEYS.has(String(row.strategy)) || row.family === 'Benchmark'
}

function rowName(row: Row): string {
  return String(row.display_name ?? row.strategy ?? '')
}

function CompareResults({
  data,
  request,
  meta,
}: {
  data: CompareResponse
  request: CompareRequest
  meta: Meta
}) {
  const c = useChartColors()
  const strategies = data.rows.filter((row) => !isBenchmark(row))
  const benchmarkRow = data.rows.find(isBenchmark)

  const leader = (key: string, higher: boolean) => {
    const valid = strategies.filter((row) => isNum(row[key]))
    if (!valid.length) return null
    return valid.reduce((best, row) =>
      higher
        ? (row[key] as number) > (best[key] as number)
          ? row
          : best
        : (row[key] as number) < (best[key] as number)
          ? row
          : best,
    )
  }
  const leaders: Array<{ label: string; key: string; higher: boolean }> = [
    { label: 'Best Sharpe', key: 'sharpe_ratio', higher: true },
    { label: 'Best total return', key: 'total_return', higher: true },
    { label: 'Best Calmar', key: 'calmar_ratio', higher: true },
    { label: 'Lowest volatility', key: 'annualized_volatility', higher: false },
    { label: 'Smallest drawdown', key: 'max_drawdown', higher: true },
  ]

  const beatBenchmark = strategies.filter(
    (row) =>
      isNum(row.sharpe_ratio) &&
      isNum(data.benchmark.sharpe_ratio) &&
      row.sharpe_ratio > data.benchmark.sharpe_ratio,
  ).length

  const points = useMemo<StrategyPoint[]>(
    () =>
      data.rows
        .filter(
          (row) => isNum(row.annualized_volatility) && isNum(row.cagr) && isNum(row.max_drawdown),
        )
        .map((row) => ({
          key: String(row.strategy),
          name: rowName(row),
          volatility: row.annualized_volatility as number,
          cagr: row.cagr as number,
          sharpe: isNum(row.sharpe_ratio) ? row.sharpe_ratio : null,
          maxDrawdown: row.max_drawdown as number,
          benchmark: isBenchmark(row),
        })),
    [data],
  )

  const objective = request.objective ? findObjective(meta, request.objective) : null
  const scatterOption = useMemo(() => riskReturnChart(c, points), [c, points])
  const barsOption = useMemo(() => drawdownBars(c, points), [c, points])

  const columns: Column[] = [
    {
      key: 'display_name',
      label: 'Strategy',
      render: (row) => (
        <span className="flex flex-col font-sans">
          <span className="font-medium text-ink">{rowName(row)}</span>
          <span className="text-[11px] text-muted">{String(row.family ?? '')}</span>
        </span>
      ),
      sortValue: rowName,
    },
    { key: 'sharpe_rank', label: '#', title: 'Rank by Sharpe ratio' },
    { key: 'total_return' },
    { key: 'cagr', label: 'CAGR' },
    { key: 'annualized_volatility' },
    { key: 'sharpe_ratio' },
    { key: 'max_drawdown' },
    { key: 'calmar_ratio' },
    { key: 'final_value' },
    { key: 'trades', title: 'Days with a change in exposure' },
    { key: 'turnover', title: 'Cumulative one-way turnover in multiples of capital' },
    { key: 'average_exposure' },
    { key: 'return_rank' },
    { key: 'volatility_rank' },
    { key: 'drawdown_rank' },
    {
      key: 'parameters',
      render: (row) => (
        <span className="font-mono text-[11px] text-muted">
          {String(row.parameters ?? '').replaceAll(' | ', ' · ')}
        </span>
      ),
    },
  ]

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <span className="font-mono font-medium text-ink">{request.ticker}</span>
        <span>{formatDateRange(request.start_date, request.end_date)}</span>
        <span aria-hidden="true">·</span>
        <span>{strategies.length} strategies</span>
        {data.in_sample ? <InSampleBadge /> : <Badge>Default parameters</Badge>}
      </div>

      {data.in_sample && (
        <Alert tone="warn" title="In-sample comparison">
          Each strategy's parameters were optimized for{' '}
          {objective?.label.toLowerCase() ?? 'the objective'} on this same sample, so these numbers
          flatter every strategy. Use Validate to see what survives out of sample.
        </Alert>
      )}

      <TileGrid className="xl:grid-cols-3 2xl:grid-cols-6">
        {leaders.map(({ label, key, higher }) => {
          const row = leader(key, higher)
          return (
            <MetricTile
              key={key}
              label={label}
              value={row ? formatMetric(key, row[key]) : '—'}
              hint={row ? rowName(row) : undefined}
            />
          )
        })}
        <MetricTile
          label="Buy and Hold Sharpe"
          value={formatRatio(data.benchmark.sharpe_ratio)}
          hint={`${beatBenchmark} of ${strategies.length} strategies beat it`}
        />
      </TileGrid>

      <EquityPanel data={data} />

      <Panel
        title="Rankings"
        description="Sorted by Sharpe ratio. Ranks run across strategies and Buy and Hold; the top Sharpe row is highlighted."
      >
        <DataTable
          caption="Strategy rankings"
          rows={data.rows}
          columns={columns}
          initialSort={{ key: 'sharpe_rank', direction: 'asc' }}
          rowTone={(row) =>
            isBenchmark(row) ? 'reference' : row.sharpe_rank === 1 ? 'best' : undefined
          }
          maxHeight={560}
        />
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel
          title="Risk versus return"
          description="CAGR against annualized volatility; Buy and Hold is the grey diamond. Hover a point for its name."
        >
          <EChart
            option={scatterOption}
            height={340}
            ariaLabel="Scatter of CAGR against volatility for each strategy"
          />
        </Panel>
        <Panel
          title="Maximum drawdown"
          description="Deepest peak-to-trough loss of each strategy, shallowest first."
        >
          <EChart
            option={barsOption}
            height={Math.max(320, points.length * 22 + 20)}
            ariaLabel="Bar chart of maximum drawdown by strategy"
          />
        </Panel>
      </div>

      {benchmarkRow && (
        <p className="text-xs text-muted">
          Buy and Hold: {formatPercent(benchmarkRow.total_return)} total return, final value{' '}
          {formatCurrency(benchmarkRow.final_value)}.
        </p>
      )}
    </>
  )
}

/** Equity and drawdown for up to four picked strategies, always against Buy and Hold. */
function EquityPanel({ data }: { data: CompareResponse }) {
  const c = useChartColors()
  const strategies = data.rows.filter(
    (row) => !isBenchmark(row) && data.equity.columns[String(row.strategy)],
  )
  const bySharpe = [...strategies].sort(
    (a, b) => Number(a.sharpe_rank ?? 99) - Number(b.sharpe_rank ?? 99),
  )
  const defaultKeys = bySharpe
    .slice(0, 3)
    .map((row) => String(row.strategy))
    .join('|')
  const defaultPicked: Record<string, number> = Object.fromEntries(
    defaultKeys
      .split('|')
      .filter(Boolean)
      .map((key, i) => [key, i]),
  )
  // Slot map: strategy key → color slot. Colors follow the strategy, never its rank.
  const [picked, setPicked] = usePageState<Record<string, number>>('compare:picked', defaultPicked)
  const effective = Object.keys(picked).some((key) => data.equity.columns[key])
    ? picked
    : defaultPicked

  const toggle = (key: string) => {
    const next = { ...effective }
    if (key in next) delete next[key]
    else {
      const used = new Set(Object.values(next))
      const slot = [0, 1, 2, 3].find((s) => !used.has(s))
      if (slot === undefined) return
      next[key] = slot
    }
    setPicked(next)
  }

  const benchmarkKey = Object.keys(data.equity.columns).find((key) => BENCHMARK_KEYS.has(key))
  const effectiveKey = JSON.stringify(effective)
  const equityOption = useMemo(() => {
    const selected = Object.entries(JSON.parse(effectiveKey) as Record<string, number>)
      .filter(([key]) => data.equity.columns[key])
      .sort((a, b) => a[1] - b[1])
    const names = new Map(data.rows.map((row) => [String(row.strategy), rowName(row)]))
    const lines = selected.map(([key, slot]) => ({
      name: names.get(key) ?? key,
      values: data.equity.columns[key],
      color: c.series[slot],
    }))
    if (benchmarkKey)
      lines.push({
        name: 'Buy and Hold',
        values: data.equity.columns[benchmarkKey],
        color: c.reference,
      })
    return {
      equity: timeLines(c, {
        dates: data.equity.dates,
        lines,
        format: (v) => formatCurrency(v),
        axisFormat: (v) => formatCurrency(v, { compact: true }),
        // The strategy chips above act as the legend.
        showLegend: false,
      }),
      drawdown: timeLines(c, {
        dates: data.equity.dates,
        lines: lines.map((line) => ({ ...line, values: drawdown(line.values) })),
        format: (v) => formatPercent(v),
        axisFormat: formatPercentTick,
        maxZero: true,
        showLegend: false,
      }),
    }
  }, [c, data, effectiveKey, benchmarkKey])

  return (
    <Panel
      title="Portfolio value"
      description={`Pick up to ${MAX_PICKED} strategies to plot against Buy and Hold (grey).`}
    >
      <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Strategies to plot">
        {bySharpe.map((row) => {
          const key = String(row.strategy)
          const slot = effective[key]
          const on = slot !== undefined
          const full = !on && Object.keys(effective).length >= MAX_PICKED
          return (
            <button
              key={key}
              type="button"
              aria-pressed={on}
              disabled={full}
              onClick={() => toggle(key)}
              className={clsx(
                'inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs transition-colors',
                on
                  ? 'border-line-strong bg-surface-2 text-ink'
                  : 'border-line text-muted hover:text-ink',
                full && 'cursor-not-allowed opacity-50 hover:text-muted',
              )}
            >
              <span
                className="h-0.5 w-3 rounded-full"
                style={{ background: on ? c.series[slot] : 'currentColor', opacity: on ? 1 : 0.4 }}
              />
              {rowName(row)}
            </button>
          )
        })}
      </div>
      <EChart
        option={equityOption.equity}
        height={320}
        ariaLabel="Portfolio value of the selected strategies and Buy and Hold"
      />
      <h3 className="mt-4 mb-1 text-[13px] font-medium text-ink-2">Drawdown</h3>
      <EChart
        option={equityOption.drawdown}
        height={200}
        ariaLabel="Drawdown of the selected strategies and Buy and Hold"
      />
    </Panel>
  )
}
