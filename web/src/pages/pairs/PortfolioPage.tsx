import { useMemo } from 'react'
import { usePairsPortfolioRun } from '@/api/client'
import type { Meta, PairsPortfolioResponse, PairsUniverseRequest } from '@/api/types'
import { EChart } from '@/charts/EChart'
import { timeLines } from '@/charts/lines'
import {
  ControlPanel,
  EmptyState,
  FieldGroup,
  ResearchLayout,
  ResultsArea,
} from '@/components/controls/ControlPanel'
import { MarketFields } from '@/components/controls/MarketFields'
import { WithMeta } from '@/components/controls/StrategyFields'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Panel } from '@/components/ui/Card'
import { DataTable } from '@/components/ui/DataTable'
import { MetricTile, MetricTiles, TileGrid } from '@/components/ui/MetricTile'
import { sameRequest } from '@/lib/equal'
import {
  formatCurrency,
  formatDate,
  formatDateRange,
  formatPercent,
  formatRatio,
  humanize,
  formatPercentTick,
} from '@/lib/format'
import { hasColumn } from '@/lib/series'
import { usePairsAssumptions } from '@/state/market'
import { useChartColors } from '@/theme/chart'
import { MethodField, MethodParamFields } from './PairsControls'
import { paramIssues, universeParams, currentParams } from './params'
import { parseTickers, usePairsForm, useUniverseForm, universeIssues } from './state'
import { UniverseFields } from './UniverseFields'
import { marketIssues } from '@/state/defaults'

export default function PortfolioPage() {
  return <WithMeta>{(meta) => <Portfolio meta={meta} />}</WithMeta>
}

function Portfolio({ meta }: { meta: Meta }) {
  const [assumptions, setAssumptions] = usePairsAssumptions()
  const [form, setForm] = usePairsForm()
  const [universe, setUniverse] = useUniverseForm()
  const run = usePairsPortfolioRun()
  const params = currentParams(form)

  const request: PairsUniverseRequest = {
    ...assumptions,
    method: form.method,
    tickers: parseTickers(universe.tickers),
    formation_years: universe.formation_years,
    top_n: universe.portfolio_top_n,
    params: universeParams(params),
  }
  const issues = [...marketIssues(assumptions), ...universeIssues(universe), ...paramIssues(params)]
  const stale = run.request !== null && !sameRequest(request, run.request)
  const submit = () => run.run(request)

  return (
    <ResearchLayout
      panel={
        <ControlPanel
          onRun={submit}
          running={run.running}
          issues={issues}
          runLabel="Build pairs portfolio"
        >
          <UniverseFields
            meta={meta}
            universe={universe}
            setUniverse={setUniverse}
            topNKey="portfolio_top_n"
          />
          <FieldGroup title="Model">
            <MethodField meta={meta} form={form} setForm={setForm} />
          </FieldGroup>
          <MethodParamFields form={form} setForm={setForm} hide={['formation_years']} collapsed />
          <MarketFields value={assumptions} onChange={setAssumptions} showTicker={false} />
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
        runningText="Selecting pairs on the opening window, then trading each one after it…"
        empty={
          <EmptyState title="An equal-weight book of pairs">
            The top pairs are selected on the opening window, then traded side by side with equal
            capital from the end of that window. No pair is chosen with knowledge of the period it
            trades.
          </EmptyState>
        }
      >
        {run.data && run.request && <PortfolioResults data={run.data} request={run.request} />}
      </ResultsArea>
    </ResearchLayout>
  )
}

function PortfolioResults({
  data,
  request,
}: {
  data: PairsPortfolioResponse
  request: PairsUniverseRequest
}) {
  const c = useChartColors()
  const equityOption = useMemo(() => {
    const pairColumns = Object.keys(data.series.columns).filter((key) => key.startsWith('equity::'))
    // Per-pair lines take categorical slots in API order (max 8); the portfolio is the ink line.
    const lines = pairColumns.map((key, i) => ({
      name: key.slice('equity::'.length),
      values: data.series.columns[key],
      color: i < c.series.length ? c.series[i] : c.reference,
      width: 1.25,
    }))
    return timeLines(c, {
      dates: data.series.dates,
      lines: [
        {
          name: 'Portfolio',
          values: data.series.columns.portfolio_equity,
          color: c.ink,
          width: 2.5,
        },
        ...lines,
      ],
      format: (v) => formatCurrency(v),
      axisFormat: (v) => formatCurrency(v, { compact: true }),
    })
  }, [c, data])

  const drawdownOption = useMemo(
    () =>
      timeLines(c, {
        dates: data.series.dates,
        lines: [
          {
            name: 'Portfolio',
            values: data.series.columns.portfolio_drawdown,
            color: c.series[0],
            area: true,
          },
        ],
        format: (v) => formatPercent(v),
        axisFormat: formatPercentTick,
        maxZero: true,
      }),
    [c, data],
  )

  const traded = data.pair_summary.filter((row) => row.status === 'traded').length

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <Badge>{humanize(request.method)}</Badge>
        <span>
          {traded} of {data.pair_summary.length} pairs traded
        </span>
        <Badge tone="accent">Out-of-sample after selection</Badge>
      </div>

      <Alert
        tone="info"
        title={`Results start after the selection window (${formatDate(data.selection_end)})`}
      >
        Pairs were chosen on {formatDateRange(data.selection_start, data.selection_end)} only.
        Everything below is measured from {formatDate(data.selection_end)} to{' '}
        {formatDate(request.end_date)}, so the selection step never saw it.
      </Alert>

      <MetricTiles metrics={data.metrics} />
      <TileGrid className="sm:grid-cols-3 2xl:grid-cols-3">
        <MetricTile
          label="Final value"
          value={formatCurrency(data.metrics.final_value)}
          hint="equal-weight book"
        />
        <MetricTile
          label="Avg pair correlation"
          value={formatRatio(data.average_pair_correlation)}
          hint="across pairs; lower diversifies"
        />
        <MetricTile
          label="Pairs traded"
          value={`${traded} / ${data.pair_summary.length}`}
          hint="skipped pairs listed below"
        />
      </TileGrid>

      <Panel
        title="Portfolio value"
        description="The equal-weight portfolio (bold) and each pair's own equity."
      >
        <EChart
          option={equityOption}
          height={340}
          ariaLabel="Pairs portfolio equity with each pair's equity"
        />
      </Panel>

      {hasColumn(data.series, 'portfolio_drawdown') && (
        <Panel title="Drawdown" description="Portfolio decline from its running peak.">
          <EChart option={drawdownOption} height={200} ariaLabel="Pairs portfolio drawdown" />
        </Panel>
      )}

      <Panel
        title="Pairs"
        description="Each selected pair's trading record after the selection window."
      >
        <DataTable
          caption="Per-pair summary"
          rows={data.pair_summary}
          rowTone={(row) => (row.status !== 'traded' ? 'reference' : undefined)}
        />
      </Panel>

      <Panel title="Selection" description="How the pairs ranked on the selection window.">
        <DataTable caption="Pair selection" rows={data.discovery} />
      </Panel>
    </>
  )
}
