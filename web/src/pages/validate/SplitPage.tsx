import { useMemo } from 'react'
import { useSplitRun } from '@/api/client'
import type { Meta, Metrics, ObjectiveMeta, Row, SplitRequest, SplitResponse } from '@/api/types'
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
import { ParamChips } from '@/components/ParamChips'
import { Badge, OutOfSampleBadge, type Tone } from '@/components/ui/Badge'
import { Panel } from '@/components/ui/Card'
import { DataTable } from '@/components/ui/DataTable'
import { DateInput } from '@/components/ui/Field'
import { sameRequest } from '@/lib/equal'
import {
  formatCurrency,
  formatDate,
  formatDateRange,
  formatMetric,
  formatPercent,
  isNum,
} from '@/lib/format'
import { cleanTicker, marketIssues } from '@/state/defaults'
import { useMarket } from '@/state/market'
import { parameterSetColor, useChartColors } from '@/theme/chart'
import { useValidateForm } from './shared'
import { findObjective, findStrategy, objectiveFormatter } from '@/lib/meta'

export default function SplitPage() {
  return <WithMeta>{(meta) => <Split meta={meta} />}</WithMeta>
}

function Split({ meta }: { meta: Meta }) {
  const [market, setMarket] = useMarket()
  const [form, setForm] = useValidateForm()
  const run = useSplitRun()
  const strategy = findStrategy(meta, form.strategy)

  const request: SplitRequest = {
    ...market,
    ticker: cleanTicker(market.ticker),
    strategy: strategy.key,
    objective: form.objective,
    split_date: form.split_date,
  }
  const issues = marketIssues(market)
  if (!(market.start_date < form.split_date && form.split_date < market.end_date))
    issues.push('The split date must fall between the start and end dates.')
  const stale = run.request !== null && !sameRequest(request, run.request)
  const submit = () => run.run(request)

  return (
    <ResearchLayout
      panel={
        <ControlPanel
          onRun={submit}
          running={run.running}
          issues={issues}
          runLabel="Run split validation"
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
          <MarketFields
            value={market}
            onChange={setMarket}
            startLabel="Training start"
            endLabel="Test end"
            betweenDates={
              <DateInput
                label="Test start (split)"
                value={form.split_date}
                onChange={(split_date) => setForm({ ...form, split_date })}
                hint="Parameters are optimized before this date and scored from it."
              />
            }
          />
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
        runningText="Optimizing on the training period, then scoring frozen parameters on the test period…"
        empty={
          <EmptyState title="Train, freeze, test">
            The sample is split at a date. The grid is searched on the earlier part only; the
            default, raw-optimum and robust parameter sets are then frozen and scored on the later,
            unseen part.
          </EmptyState>
        }
      >
        {run.data && run.request && (
          <SplitResults data={run.data} request={run.request} meta={meta} />
        )}
      </ResultsArea>
    </ResearchLayout>
  )
}

const ROBUSTNESS_TONE: Record<string, Tone> = {
  'Broad plateau': 'pos',
  'Moderate plateau': 'accent',
  'Narrow peak': 'warn',
}

function isBuyHold(label: string): boolean {
  const l = label.toLowerCase()
  return l.includes('buy') || l === 'buy_hold'
}

/** Best row by test objective in the objective's direction. */
function bestIndex(rows: Row[], key: string, objective: ObjectiveMeta): number {
  let best = -1
  rows.forEach((row, i) => {
    const v = row[key]
    if (!isNum(v) || isBuyHold(String(row.parameter_set ?? ''))) return
    const current = best >= 0 ? (rows[best][key] as number) : null
    if (current === null || (objective.higher_is_better ? v > current : v < current)) best = i
  })
  return best
}

function SplitResults({
  data,
  request,
  meta,
}: {
  data: SplitResponse
  request: SplitRequest
  meta: Meta
}) {
  const c = useChartColors()
  const strategy = findStrategy(meta, request.strategy)
  const objective = findObjective(meta, request.objective ?? 'sharpe_ratio')
  const format = useMemo(() => objectiveFormatter(objective), [objective])

  const equityOption = useMemo(
    () =>
      timeLines(c, {
        dates: data.test_equity.dates,
        lines: Object.keys(data.test_equity.columns).map((name, i) => ({
          name: name === 'buy_hold' ? 'Buy and Hold' : name,
          values: data.test_equity.columns[name],
          color: parameterSetColor(c, name, i),
        })),
        format: (v) => formatCurrency(v),
        axisFormat: (v) => formatCurrency(v, { compact: true }),
        reference: { value: request.initial_capital ?? 10_000 },
      }),
    [c, data, request.initial_capital],
  )

  const sets: Array<{
    label: string
    parameters?: Record<string, number>
    training: Metrics
    test: Metrics
  }> = [
    ...data.parameter_sets.map((set) => ({
      label: set.label,
      parameters: set.parameters,
      training: set.training_metrics,
      test: set.test_metrics,
    })),
    {
      label: 'Buy and Hold',
      training: data.benchmark.training_metrics,
      test: data.benchmark.test_metrics,
    },
  ]
  const defaults = data.parameter_sets.find((set) =>
    set.label.toLowerCase().includes('default'),
  )?.parameters
  const best = bestIndex(data.summary, 'test_objective', objective)

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <span className="font-semibold text-ink">{strategy.display_name}</span>
        <span className="font-mono font-medium text-ink">{request.ticker}</span>
        <OutOfSampleBadge />
        <Badge>{objective.label}</Badge>
        <Badge
          tone={ROBUSTNESS_TONE[data.robustness_label] ?? 'neutral'}
          title="Shape of the training optimization surface"
        >
          Training surface: {data.robustness_label}
        </Badge>
      </div>

      <Timeline
        start={request.start_date}
        evaluationStart={data.training_evaluation_start}
        split={data.split_date}
        end={request.end_date}
      />

      <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
        {sets.map((set, i) => {
          const train = set.training[objective.key]
          const test = set.test[objective.key]
          return (
            <article
              key={set.label}
              className="min-w-0 rounded-xl border border-line bg-surface p-4 shadow-card"
            >
              <header className="flex items-center gap-2">
                <span
                  className="h-0.5 w-3.5 rounded-full"
                  style={{ background: parameterSetColor(c, set.label, i) }}
                />
                <h3 className="text-[13px] font-semibold text-ink">{set.label}</h3>
              </header>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div>
                  <p className="text-[11px] text-muted">Training</p>
                  <p className="num font-mono text-sm text-ink-2">
                    {isNum(train) ? format(train) : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] text-muted">Test</p>
                  <p className="num font-mono text-lg font-semibold text-ink">
                    {isNum(test) ? format(test) : '—'}
                  </p>
                </div>
              </div>
              <p className="num mt-1 text-xs text-muted">
                Test return {formatPercent(set.test.total_return)} · max DD{' '}
                {formatMetric('max_drawdown', set.test.max_drawdown)}
              </p>
              {set.parameters && (
                <ParamChips
                  className="mt-3"
                  parameters={set.parameters}
                  specs={strategy.parameters}
                  baseline={defaults}
                />
              )}
            </article>
          )
        })}
      </div>

      <Panel
        title="Out-of-sample equity"
        description={`Each frozen parameter set from ${formatDate(data.split_date)}, rebased to the initial capital.`}
      >
        <EChart
          option={equityOption}
          height={320}
          ariaLabel="Test-period equity of each parameter set and Buy and Hold"
        />
      </Panel>

      <Panel
        title="Training vs test"
        description={`Objective in training and test. OOS degradation is how much worse the test value is than training, in the objective's direction (negative = improved out of sample). The best test ${objective.label.toLowerCase()} is highlighted.`}
      >
        <DataTable
          caption="Validation summary"
          rows={data.summary}
          objectiveFormat={objective.format}
          rowTone={(row, i) =>
            isBuyHold(String(row.parameter_set ?? ''))
              ? 'reference'
              : i === best
                ? 'best'
                : undefined
          }
        />
      </Panel>
    </>
  )
}

/** Proportional bar showing burn-in, training and test periods. */
function Timeline({
  start,
  evaluationStart,
  split,
  end,
}: {
  start: string
  evaluationStart: string
  split: string
  end: string
}) {
  const t = (d: string) => new Date(`${d.slice(0, 10)}T00:00:00Z`).getTime()
  const total = Math.max(t(end) - t(start), 1)
  const pct = (a: string, b: string) => `${Math.max(((t(b) - t(a)) / total) * 100, 0)}%`
  return (
    <div className="rounded-xl border border-line bg-surface p-4 shadow-card">
      <div className="flex h-2.5 overflow-hidden rounded-full" aria-hidden="true">
        <div className="bg-surface-3" style={{ width: pct(start, evaluationStart) }} />
        <div className="bg-accent/45" style={{ width: pct(evaluationStart, split) }} />
        <div className="bg-accent" style={{ width: pct(split, end) }} />
      </div>
      <dl className="mt-3 grid gap-x-6 gap-y-1 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-muted">Burn-in (indicator warm-up)</dt>
          <dd className="num text-ink-2">{formatDateRange(start, evaluationStart)}</dd>
        </div>
        <div>
          <dt className="text-muted">Training — parameters selected</dt>
          <dd className="num text-ink-2">{formatDateRange(evaluationStart, split)}</dd>
        </div>
        <div>
          <dt className="font-medium text-ink">Test — parameters frozen</dt>
          <dd className="num text-ink">{formatDateRange(split, end)}</dd>
        </div>
      </dl>
    </div>
  )
}
