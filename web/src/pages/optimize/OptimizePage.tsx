import { useMemo } from 'react'
import { useOptimizeRun } from '@/api/client'
import type {
  Grid,
  Meta,
  OptimizeRequest,
  OptimizeResponse,
  Parameters,
  Row,
  StrategyMeta,
} from '@/api/types'
import { EChart } from '@/charts/EChart'
import { heatmapChart } from '@/charts/heatmap'
import { profileChart } from '@/charts/profiles'
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
import { PageBody, PageHeader } from '@/components/shell/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Badge, InSampleBadge, type Tone } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Panel } from '@/components/ui/Card'
import { DataTable, type Column } from '@/components/ui/DataTable'
import { NumberInput, Segmented, TextInput } from '@/components/ui/Field'
import { MetricTile, MetricTiles, TileGrid } from '@/components/ui/MetricTile'
import { sameRequest } from '@/lib/equal'
import {
  formatDate,
  formatDateRange,
  formatInteger,
  formatParameterValue,
  formatPercent,
  formatSignedPercent,
  humanize,
  isNum,
} from '@/lib/format'
import { cleanTicker, marketIssues } from '@/state/defaults'
import { useMarket } from '@/state/market'
import { DEFAULT_OPTIMIZE_FORM, type OptimizeForm } from '@/state/forms'
import { usePageState } from '@/state/store'
import { useChartColors } from '@/theme/chart'
import { findObjective, findStrategy, objectiveFormatter } from '@/lib/meta'

const MAX_COMBINATIONS = 5000

export default function OptimizePage() {
  return (
    <>
      <PageHeader
        title="Optimize"
        description="Search a parameter grid for the historical optimum, then ask whether it sits on a broad plateau or an isolated peak — and how much of it the number of trials explains."
        badges={<InSampleBadge />}
      />
      <PageBody>
        <WithMeta>{(meta) => <Optimize meta={meta} />}</WithMeta>
      </PageBody>
    </>
  )
}

function gridText(values: number[]): string {
  return values.map((v) => String(v)).join(', ')
}

/** Parse a custom grid; returns the grid and per-parameter errors. */
function parseGrid(
  strategy: StrategyMeta,
  text: Record<string, string> | undefined,
): { grid: Grid; errors: Record<string, string> } {
  const grid: Grid = {}
  const errors: Record<string, string> = {}
  for (const [key, spec] of Object.entries(strategy.parameters)) {
    const raw = text?.[key] ?? gridText(strategy.default_grid[key] ?? [spec.default])
    const parts = raw
      .split(/[,\s]+/)
      .map((part) => part.trim())
      .filter(Boolean)
    const values = parts.map(Number)
    if (!parts.length) errors[key] = 'Enter at least one value'
    else if (values.some((v) => !Number.isFinite(v))) errors[key] = 'Numbers only, comma-separated'
    else if (spec.type === 'int' && values.some((v) => !Number.isInteger(v)))
      errors[key] = 'Whole numbers only'
    else if (values.some((v) => v < spec.min || v > spec.max))
      errors[key] = `Values must be within ${spec.min}–${spec.max}`
    grid[key] = [...new Set(values)].sort((a, b) => a - b)
  }
  return { grid, errors }
}

function gridSize(grid: Grid): number {
  return Object.values(grid).reduce((total, values) => total * Math.max(values.length, 1), 1)
}

function Optimize({ meta }: { meta: Meta }) {
  const [market, setMarket] = useMarket()
  const [form, setForm] = usePageState<OptimizeForm>('optimize:form', DEFAULT_OPTIMIZE_FORM)
  const run = useOptimizeRun()
  const strategy = findStrategy(meta, form.strategy)
  const { grid: customGrid, errors: gridErrors } = parseGrid(strategy, form.custom[strategy.key])
  const searchGrid = form.mode === 'custom' ? customGrid : strategy.default_grid
  const size = gridSize(searchGrid)
  const paramCount = Object.keys(searchGrid).length

  const request: OptimizeRequest = {
    ...market,
    ticker: cleanTicker(market.ticker),
    strategy: strategy.key,
    objective: form.objective,
    mode: form.mode,
    grid: form.mode === 'custom' ? customGrid : undefined,
    refinement_points: form.mode === 'coarse_to_fine' ? form.refinement_points : undefined,
  }
  const issues = [...marketIssues(market)]
  if (form.mode === 'custom' && Object.keys(gridErrors).length) issues.push('Fix the custom grid.')
  if (size > MAX_COMBINATIONS)
    issues.push(
      `The grid has ${formatInteger(size)} combinations; the limit is ${formatInteger(MAX_COMBINATIONS)}.`,
    )
  const stale = run.request !== null && !sameRequest(request, run.request)
  const submit = () => run.run(request)

  const setCustom = (key: string, value: string) =>
    setForm({
      ...form,
      custom: { ...form.custom, [strategy.key]: { ...form.custom[strategy.key], [key]: value } },
    })

  return (
    <ResearchLayout
      panel={
        <ControlPanel
          onRun={submit}
          running={run.running}
          issues={issues}
          runLabel="Run optimization"
        >
          <FieldGroup title="Search">
            <StrategySelect
              meta={meta}
              value={strategy.key}
              onChange={(key) => setForm({ ...form, strategy: key })}
            />
            <ObjectiveSelect
              meta={meta}
              value={form.objective}
              onChange={(objective) => setForm({ ...form, objective })}
            />
            <Segmented
              label="Grid"
              value={form.mode}
              onChange={(mode) => setForm({ ...form, mode })}
              options={[
                { value: 'predefined', label: 'Predefined' },
                { value: 'custom', label: 'Custom' },
                { value: 'coarse_to_fine', label: 'Coarse→fine' },
              ]}
              size="sm"
            />
            {form.mode === 'custom' && (
              <div className="space-y-3">
                {Object.entries(strategy.parameters).map(([key, spec]) => (
                  <TextInput
                    key={`${strategy.key}:${key}`}
                    label={spec.label}
                    value={
                      form.custom[strategy.key]?.[key] ??
                      gridText(strategy.default_grid[key] ?? [spec.default])
                    }
                    onChange={(value) => setCustom(key, value)}
                    mono
                    error={gridErrors[key]}
                    hint={`${spec.min}–${spec.max}${spec.format === 'percent' ? ' as decimals (0.15 = 15%)' : ''}`}
                  />
                ))}
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    setForm({ ...form, custom: { ...form.custom, [strategy.key]: {} } })
                  }
                >
                  Reset to predefined grid
                </Button>
              </div>
            )}
            {form.mode === 'coarse_to_fine' && (
              <NumberInput
                label="Refinement points per parameter"
                value={form.refinement_points}
                onChange={(refinement_points) => setForm({ ...form, refinement_points })}
                min={3}
                max={9}
                step={1}
                integer
                hint="Stage 2 interpolates this many values around the broad-stage winner."
              />
            )}
            <p className="num rounded-md bg-surface-2 px-2.5 py-1.5 text-xs text-ink-2">
              {form.mode === 'coarse_to_fine' ? 'Stage 1: ' : ''}
              <span className="font-mono font-medium text-ink">{formatInteger(size)}</span>{' '}
              combinations
              {form.mode === 'coarse_to_fine' && (
                <>
                  {' · Stage 2: up to '}
                  <span className="font-mono font-medium text-ink">
                    {formatInteger(
                      Math.min(form.refinement_points ** paramCount, MAX_COMBINATIONS),
                    )}
                  </span>
                </>
              )}
            </p>
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
        runningText={`Evaluating ${formatInteger(size)}${form.mode === 'coarse_to_fine' ? '+' : ''} parameter combinations…`}
        empty={
          <EmptyState title="Search a parameter grid">
            Every candidate is scored from the same date, after the grid's longest lookback, so
            short and long windows compete on the same observations. The result is in-sample by
            construction.
          </EmptyState>
        }
      >
        {run.data && run.request && (
          <OptimizeResults data={run.data} request={run.request} meta={meta} />
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

function sameParams(row: Row, params: Parameters | null): boolean {
  if (!params) return false
  return Object.entries(params).every(([key, value]) => row[key] === value)
}

function asParams(value: unknown): Parameters | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Parameters
}

function OptimizeResults({
  data,
  request,
  meta,
}: {
  data: OptimizeResponse
  request: OptimizeRequest
  meta: Meta
}) {
  const c = useChartColors()
  const strategy = findStrategy(meta, request.strategy)
  const objective = findObjective(meta, data.objective)
  const format = useMemo(() => objectiveFormatter(objective), [objective])
  const robust = data.robustness as Record<string, unknown>
  const robustParams = asParams(robust.robust_candidate_parameters)
  const boundary = Array.isArray(robust.boundary_parameters)
    ? (robust.boundary_parameters as string[])
    : []
  const robustnessLabel = String(robust.robustness_label ?? '—')
  const best = data.best_metrics[data.objective]
  const fallback = data.default_metrics[data.objective]
  const paramKeys = Object.keys(data.best_parameters)

  const heatmapOption = useMemo(
    () =>
      data.heatmap
        ? heatmapChart(c, data.heatmap, {
            format,
            higherIsBetter: objective.higher_is_better,
            objectiveLabel: objective.label,
            best: {
              x: data.best_parameters[data.heatmap.x_parameter],
              y: data.best_parameters[data.heatmap.y_parameter],
            },
            specs: strategy.parameters,
          })
        : null,
    [c, data, objective, strategy.parameters, format],
  )

  const profileOptions = useMemo(
    () =>
      Object.entries(data.profiles)
        .filter(([, points]) => points.length > 1)
        .map(([parameter, points]) => ({
          parameter,
          option: profileChart(c, parameter, points, {
            format,
            selected: data.best_parameters[parameter],
            spec: strategy.parameters[parameter],
          }),
        })),
    [c, data, strategy.parameters, format],
  )

  const columns: Column[] = [
    {
      key: '__pick',
      label: '',
      kind: 'text',
      render: (row) =>
        sameParams(row, data.best_parameters) ? (
          <Badge tone="accent">Optimum</Badge>
        ) : sameParams(row, robustParams) ? (
          <Badge tone="pos">Robust</Badge>
        ) : null,
      sortValue: () => null,
    },
    ...paramKeys.map((key) => ({
      key,
      label: strategy.parameters[key]?.label ?? humanize(key),
      kind: 'text' as const,
      align: 'right' as const,
      render: (row: Row) => (
        <span className="num font-mono text-[12px]">
          {formatParameterValue(row[key], strategy.parameters[key])}
        </span>
      ),
      sortValue: (row: Row) => (isNum(row[key]) ? (row[key] as number) : null),
    })),
    { key: data.objective, highlight: true },
    ...[
      'total_return',
      'cagr',
      'annualized_volatility',
      'sharpe_ratio',
      'max_drawdown',
      'calmar_ratio',
      'final_value',
      'rebalancing_days',
      'turnover',
    ]
      .filter((key) => key !== data.objective)
      .map((key) => ({ key })),
  ]

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <span className="font-semibold text-ink">{strategy.display_name}</span>
        <span className="font-mono font-medium text-ink">{request.ticker}</span>
        <span>{formatDateRange(request.start_date, request.end_date)}</span>
        <InSampleBadge />
        <Badge>{objective.label}</Badge>
        {request.mode === 'coarse_to_fine' && <Badge>Coarse → fine</Badge>}
      </div>

      <Alert tone="info" title={`Scored from ${formatDate(data.evaluation_start)}`}>
        Every candidate is evaluated from this date — after the longest lookback in the grid — so
        all parameter sets compete on the same observations. Earlier rows only warm up indicators.
      </Alert>

      <TileGrid className="xl:grid-cols-3 2xl:grid-cols-6">
        <MetricTile
          label={`Optimum ${objective.label.toLowerCase()}`}
          value={format(best as number)}
          delta={
            isNum(data.optimization_gain)
              ? `${data.optimization_gain >= 0 ? '+' : ''}${format(data.optimization_gain)}`
              : undefined
          }
          deltaTone={
            isNum(data.optimization_gain) && data.optimization_gain > 0 ? 'pos' : 'neutral'
          }
          deltaLabel="vs defaults"
          emphasis
        />
        <MetricTile
          label={`Default ${objective.label.toLowerCase()}`}
          value={isNum(fallback) ? format(fallback) : '—'}
          hint="registry defaults"
        />
        <MetricTile
          label="Relative gain"
          value={formatSignedPercent(data.relative_optimization_gain)}
          hint="optimum vs defaults"
        />
        <MetricTile
          label="Combinations tested"
          value={formatInteger(data.combinations_tested)}
          hint={
            data.stages
              ? `${formatInteger(data.stages.broad_combinations)} broad + ${formatInteger(data.stages.refined_combinations)} refined`
              : 'valid grid points'
          }
        />
        <MetricTile
          label="Probabilistic Sharpe"
          value={formatPercent(data.probabilistic_sharpe_ratio)}
          hint="P(true Sharpe > 0)"
        />
        <MetricTile
          label="Deflated Sharpe"
          value={formatPercent(data.deflated_sharpe_ratio)}
          hint={
            isNum(data.deflated_sharpe_ratio) && data.deflated_sharpe_ratio < 0.95
              ? `weak after ${formatInteger(data.combinations_tested)} trials`
              : `after ${formatInteger(data.combinations_tested)} trials`
          }
        />
      </TileGrid>
      <p className="-mt-1 text-xs leading-relaxed text-muted">
        <span className="font-medium text-ink-2">Probabilistic Sharpe</span> is the probability that
        the optimum's true Sharpe ratio is above zero, given the sample length and the skew and fat
        tails of its returns. <span className="font-medium text-ink-2">Deflated Sharpe</span> asks
        the same after accounting for every combination tried — the more trials, the higher the bar
        a lucky optimum must clear. Values below ~95% are weak evidence.
      </p>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Panel
          title="Parameter sets"
          description="Raw optimum and the stability-oriented candidate against the defaults."
        >
          <dl className="space-y-3">
            <ParamRow
              label="Raw optimum"
              tone="accent"
              params={data.best_parameters}
              strategy={strategy}
              baseline={data.default_parameters}
              value={format(best as number)}
            />
            {robustParams && (
              <ParamRow
                label="Robust candidate"
                tone="pos"
                params={robustParams}
                strategy={strategy}
                baseline={data.default_parameters}
                value={
                  isNum(robust.robust_candidate_objective)
                    ? format(robust.robust_candidate_objective)
                    : '—'
                }
                note={
                  isNum(robust.robust_candidate_local_median_objective)
                    ? `neighborhood median ${format(robust.robust_candidate_local_median_objective)}`
                    : undefined
                }
              />
            )}
            <ParamRow
              label="Defaults"
              tone="neutral"
              params={data.default_parameters}
              strategy={strategy}
              value={isNum(fallback) ? format(fallback) : '—'}
            />
          </dl>
        </Panel>

        <Panel
          title="Robustness"
          description="Shape of the tested surface around the optimum — descriptive heuristics, not proof."
          actions={
            <Badge tone={ROBUSTNESS_TONE[robustnessLabel] ?? 'neutral'}>{robustnessLabel}</Badge>
          }
        >
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-[13px]">
            <Stat
              label="Within 5% of optimum"
              value={formatPercent(robust.near_optimal_5_share)}
              note={`${formatInteger(robust.near_optimal_5_count)} combos`}
            />
            <Stat
              label="Within 10% of optimum"
              value={formatPercent(robust.near_optimal_10_share)}
              note={`${formatInteger(robust.near_optimal_10_count)} combos`}
            />
            <Stat
              label="Neighbors within 10%"
              value={formatPercent(robust.local_near_optimal_10_share)}
              note={`of ${formatInteger(robust.local_neighbor_count)} neighbors`}
            />
            <Stat
              label="Median neighbor drop"
              value={formatPercent(robust.local_median_relative_degradation)}
            />
            <Stat
              label="Gap to runner-up"
              value={formatPercent(robust.best_to_second_relative_gap)}
            />
            <Stat label="Selection risk" value={String(robust.selection_risk_label ?? '—')} />
          </dl>
          {boundary.length > 0 && (
            <Alert tone="warn" className="mt-3">
              The optimum sits on the edge of the grid for {boundary.map(humanize).join(', ')}. The
              true optimum may lie outside the tested range.
            </Alert>
          )}
        </Panel>
      </div>

      <Panel
        title="Optimum vs defaults"
        description="Full metrics of the raw optimum, with the change from the default parameters."
      >
        <MetricTiles
          metrics={data.best_metrics}
          reference={data.default_metrics}
          referenceLabel="vs defaults"
        />
      </Panel>

      {data.stages && (
        <Panel
          title="Coarse-to-fine stages"
          description="Stage 1 searches the broad grid; stage 2 refines around its winner."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-xs font-medium text-muted">
                Stage 1 · {formatInteger(data.stages.broad_combinations)} combinations · winner
              </p>
              <ParamChips
                className="mt-2"
                parameters={data.stages.broad_best_parameters}
                specs={strategy.parameters}
              />
            </div>
            <div>
              <p className="text-xs font-medium text-muted">
                Stage 2 · {formatInteger(data.stages.refined_combinations)} combinations · refined
                grid
              </p>
              <dl className="mt-2 space-y-1 text-xs">
                {Object.entries(data.stages.refined_grid).map(([key, values]) => (
                  <div key={key} className="flex gap-2">
                    <dt className="w-32 shrink-0 truncate text-muted">
                      {strategy.parameters[key]?.label ?? humanize(key)}
                    </dt>
                    <dd className="num min-w-0 font-mono break-words text-ink">
                      {values
                        .map((v) => formatParameterValue(v, strategy.parameters[key]))
                        .join(', ')}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </Panel>
      )}

      {heatmapOption && data.heatmap && (
        <Panel
          title="Sensitivity heatmap"
          description={`Best ${objective.label.toLowerCase()} for each ${humanize(data.heatmap.x_parameter).toLowerCase()} × ${humanize(data.heatmap.y_parameter).toLowerCase()} pair (over any other parameters). The legend shows which end of the scale is better; ★ marks the optimum; blank cells are invalid combinations.`}
        >
          <EChart
            option={heatmapOption}
            height={Math.min(560, Math.max(320, data.heatmap.y_values.length * 34 + 110))}
            ariaLabel="Heatmap of the objective across two parameters"
          />
        </Panel>
      )}

      {profileOptions.length > 0 && (
        <Panel
          title="Parameter profiles"
          description="For each value of one parameter: the best and the median objective across all other parameters. A flat best line means the result does not hinge on the exact value."
        >
          <div className="grid gap-4 md:grid-cols-2">
            {profileOptions.map(({ parameter, option }) => (
              <EChart
                key={parameter}
                option={option}
                height={220}
                ariaLabel={`Objective profile for ${humanize(parameter)}`}
              />
            ))}
          </div>
        </Panel>
      )}

      <Panel
        title="Ranked combinations"
        description={`Best first${data.results.length >= 500 ? ' (top 500 shown)' : ''}. The objective column is emphasized.`}
      >
        <DataTable
          caption="Ranked parameter combinations"
          rows={data.results}
          columns={columns}
          objectiveFormat={objective.format}
          rowTone={(_row, index) => (index === 0 ? 'best' : undefined)}
          maxHeight={480}
        />
      </Panel>
    </>
  )
}

function ParamRow({
  label,
  tone,
  params,
  strategy,
  baseline,
  value,
  note,
}: {
  label: string
  tone: Tone
  params: Parameters
  strategy: StrategyMeta
  baseline?: Parameters
  value: string
  note?: string
}) {
  return (
    <div className="rounded-lg border border-line p-3">
      <dt className="flex items-center justify-between gap-2">
        <Badge tone={tone}>{label}</Badge>
        <span className="num text-right font-mono text-sm font-semibold text-ink">
          {value}
          {note && <span className="block text-[11px] font-normal text-muted">{note}</span>}
        </span>
      </dt>
      <dd className="mt-2">
        <ParamChips parameters={params} specs={strategy.parameters} baseline={baseline} />
      </dd>
    </div>
  )
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-xs text-muted">{label}</dt>
      <dd className="num font-mono text-[13px] font-medium text-ink">
        {value}
        {note && (
          <span className="ml-1.5 font-sans text-[11px] font-normal text-muted">{note}</span>
        )}
      </dd>
    </div>
  )
}
