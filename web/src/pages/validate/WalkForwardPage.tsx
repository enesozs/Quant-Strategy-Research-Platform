import { useMemo } from 'react'
import { useWalkForwardRun } from '@/api/client'
import type { Meta, Row, WalkForwardRequest, WalkForwardResponse } from '@/api/types'
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
import { ObjectiveSelect, StrategySelect, WithMeta } from '@/components/controls/StrategyFields'
import { Badge, OutOfSampleBadge } from '@/components/ui/Badge'
import { Panel } from '@/components/ui/Card'
import { DataTable, type Column } from '@/components/ui/DataTable'
import { NumberInput, Segmented } from '@/components/ui/Field'
import { MetricTile, TileGrid } from '@/components/ui/MetricTile'
import { sameRequest } from '@/lib/equal'
import { columnLabel } from '@/lib/columns'
import {
  formatCurrency,
  formatDateRange,
  formatPercent,
  formatParameterValue,
  isNum,
} from '@/lib/format'
import { cleanTicker, marketIssues } from '@/state/defaults'
import { useMarket } from '@/state/market'
import { parameterSetColor, useChartColors } from '@/theme/chart'
import { useValidateForm } from './shared'
import { findObjective, findStrategy } from '@/lib/meta'

export default function WalkForwardPage() {
  return <WithMeta>{(meta) => <WalkForward meta={meta} />}</WithMeta>
}

function WalkForward({ meta }: { meta: Meta }) {
  const [market, setMarket] = useMarket()
  const [form, setForm] = useValidateForm()
  const run = useWalkForwardRun()
  const strategy = findStrategy(meta, form.strategy)

  const request: WalkForwardRequest = {
    ...market,
    ticker: cleanTicker(market.ticker),
    strategy: strategy.key,
    objective: form.objective,
    window_type: form.window_type,
    initial_training_years: form.initial_training_years,
    test_window_years: form.test_window_years,
  }
  const issues = marketIssues(market)
  const years =
    (new Date(market.end_date).getTime() - new Date(market.start_date).getTime()) / (365.25 * 864e5)
  if (years < form.initial_training_years + form.test_window_years)
    issues.push('The sample is too short for one training window plus one test window.')
  const stale = run.request !== null && !sameRequest(request, run.request)
  const submit = () => run.run(request)

  return (
    <ResearchLayout
      panel={
        <ControlPanel
          onRun={submit}
          running={run.running}
          issues={issues}
          runLabel="Run walk-forward"
        >
          <FieldGroup title="Strategy">
            <StrategySelect
              meta={meta}
              value={strategy.key}
              onChange={(key) => setForm({ ...form, strategy: key })}
            />
            <ObjectiveSelect
              meta={meta}
              value={form.objective}
              onChange={(objective) => setForm({ ...form, objective })}
              label="Training objective"
            />
          </FieldGroup>
          <FieldGroup title="Folds">
            <Segmented
              label="Training window"
              value={form.window_type}
              onChange={(window_type) => setForm({ ...form, window_type })}
              options={[
                { value: 'expanding', label: 'Expanding' },
                { value: 'rolling', label: 'Rolling' },
              ]}
            />
            <p className="text-xs leading-snug text-muted">
              {form.window_type === 'expanding'
                ? 'Each fold keeps the original start and adds all history before its test window.'
                : 'Each fold trains on a fixed-length window right before its test window; old data drops out.'}
            </p>
            <div className="grid grid-cols-2 items-end gap-3">
              <NumberInput
                label={
                  form.window_type === 'rolling' ? 'Training (years)' : 'Initial training (years)'
                }
                value={form.initial_training_years}
                onChange={(initial_training_years) => setForm({ ...form, initial_training_years })}
                min={1}
                max={20}
                step={1}
                integer
              />
              <NumberInput
                label="Test window (years)"
                value={form.test_window_years}
                onChange={(test_window_years) => setForm({ ...form, test_window_years })}
                min={1}
                max={10}
                step={1}
                integer
              />
            </div>
          </FieldGroup>
          <MarketFields value={market} onChange={setMarket} />
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
        runningText="Re-optimizing on each training window and scoring the next unseen window…"
        empty={
          <EmptyState title="Repeat the train → test cycle">
            The grid is re-optimized before every test window using only earlier data, and the
            unseen windows are stitched into one continuous out-of-sample record.
          </EmptyState>
        }
      >
        {run.data && run.request && (
          <WalkForwardResults data={run.data} request={run.request} meta={meta} />
        )}
      </ResultsArea>
    </ResearchLayout>
  )
}

function WalkForwardResults({
  data,
  request,
  meta,
}: {
  data: WalkForwardResponse
  request: WalkForwardRequest
  meta: Meta
}) {
  const c = useChartColors()
  const strategy = findStrategy(meta, request.strategy)
  const objective = findObjective(meta, request.objective ?? 'sharpe_ratio')

  const equityOption = useMemo(
    () =>
      timeLines(c, {
        dates: data.stitched_equity.dates,
        lines: Object.keys(data.stitched_equity.columns).map((name, i) => ({
          name: name === 'buy_hold' ? 'Buy and Hold' : name,
          values: data.stitched_equity.columns[name],
          color: parameterSetColor(c, name, i),
        })),
        format: (v) => formatCurrency(v),
        axisFormat: (v) => formatCurrency(v, { compact: true }),
        reference: { value: request.initial_capital ?? 10_000 },
      }),
    [c, data, request.initial_capital],
  )

  const aggregate = (label: string) =>
    data.aggregate.find((row) => String(row.parameter_set).toLowerCase().includes(label))
  const raw = aggregate('raw')
  const robust = aggregate('robust')
  const benchmark = aggregate('buy')
  const share = (key: string) => {
    const values = data.folds.map((row) => row[key]).filter((v) => typeof v === 'boolean')
    return values.length ? values.filter(Boolean).length / values.length : null
  }

  const bestAggregate = (() => {
    let best = -1
    data.aggregate.forEach((row, i) => {
      const v = row.median_test_objective
      if (!isNum(v) || String(row.parameter_set).toLowerCase().includes('buy')) return
      const current = best >= 0 ? (data.aggregate[best].median_test_objective as number) : null
      if (current === null || (objective.higher_is_better ? v > current : v < current)) best = i
    })
    return best
  })()

  const historyColumns: Column[] = Object.keys(data.parameter_history[0] ?? {}).map((key) => {
    const match = /^(raw|robust)_(.+)$/.exec(key)
    if (!match || !strategy.parameters[match[2]]) return { key }
    const spec = strategy.parameters[match[2]]
    return {
      key,
      label: `${match[1] === 'raw' ? 'Raw' : 'Robust'} · ${spec.label}`,
      kind: 'number',
      render: (row: Row) => formatParameterValue(row[key], spec),
    }
  })

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <span className="font-semibold text-ink">{strategy.display_name}</span>
        <span className="font-mono font-medium text-ink">{request.ticker}</span>
        <span>{formatDateRange(request.start_date, request.end_date)}</span>
        <OutOfSampleBadge />
        <Badge>{objective.label}</Badge>
        <Badge>
          {request.window_type === 'rolling' ? 'Rolling' : 'Expanding'} · {data.folds.length} folds
        </Badge>
      </div>

      <TileGrid className="xl:grid-cols-3 2xl:grid-cols-6">
        <MetricTile
          label="Raw optimum, stitched"
          value={formatPercent(raw?.stitched_total_return)}
          hint={`CAGR ${formatPercent(raw?.stitched_cagr)}`}
        />
        <MetricTile
          label="Robust candidate, stitched"
          value={formatPercent(robust?.stitched_total_return)}
          hint={`CAGR ${formatPercent(robust?.stitched_cagr)}`}
        />
        <MetricTile
          label="Buy and Hold, stitched"
          value={formatPercent(benchmark?.stitched_total_return)}
          hint={`CAGR ${formatPercent(benchmark?.stitched_cagr)}`}
        />
        <MetricTile
          label="Raw beats defaults"
          value={formatPercent(share('raw_beats_default'), 0)}
          hint="share of test folds"
        />
        <MetricTile
          label="Robust beats defaults"
          value={formatPercent(share('robust_beats_default'), 0)}
          hint="share of test folds"
        />
        <MetricTile
          label="Robust beats raw"
          value={formatPercent(share('robust_beats_raw'), 0)}
          hint="share of test folds"
        />
      </TileGrid>

      <Panel
        title="Stitched out-of-sample equity"
        description="Only unseen test windows, compounded into one continuous curve. Costs at fold boundaries apply to the actual change in exposure."
      >
        <EChart
          option={equityOption}
          height={320}
          ariaLabel="Stitched out-of-sample equity for each parameter set"
        />
      </Panel>

      <Panel
        title="Aggregate evidence"
        description={`Test ${objective.label.toLowerCase()} across folds. The best median among the parameter sets is highlighted.`}
      >
        <DataTable
          caption="Aggregate walk-forward summary"
          rows={data.aggregate}
          objectiveFormat={objective.format}
          rowTone={(row, i) =>
            String(row.parameter_set).toLowerCase().includes('buy')
              ? 'reference'
              : i === bestAggregate
                ? 'best'
                : undefined
          }
        />
      </Panel>

      <Panel
        title="Fold by fold"
        description="Each row optimizes on its training window and scores the following test window."
      >
        <DataTable
          caption="Walk-forward folds"
          rows={data.folds}
          objectiveFormat={objective.format}
          columns={Object.keys(data.folds[0] ?? {}).map((key) => ({
            key,
            label: columnLabel(key),
          }))}
        />
      </Panel>

      <Panel
        title="Parameter stability"
        description="Parameters chosen in each fold. Large jumps between folds suggest the optimum is chasing noise."
      >
        <DataTable
          caption="Parameter history"
          rows={data.parameter_history}
          columns={historyColumns}
        />
      </Panel>
    </>
  )
}
