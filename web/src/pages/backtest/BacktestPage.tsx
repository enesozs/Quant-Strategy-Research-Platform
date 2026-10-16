import { useMemo } from 'react'
import { useBacktestRun } from '@/api/client'
import type { BacktestRequest, BacktestResponse, Meta, Metrics } from '@/api/types'
import { EChart } from '@/charts/EChart'
import { timeLines } from '@/charts/lines'
import { priceChart } from '@/charts/price'
import {
  ControlPanel,
  EmptyState,
  FieldGroup,
  ResearchLayout,
  ResultsArea,
} from '@/components/controls/ControlPanel'
import { MarketFields } from '@/components/controls/MarketFields'
import { ParameterFields, StrategySelect, WithMeta } from '@/components/controls/StrategyFields'
import { ParamChips } from '@/components/ParamChips'
import { PageBody, PageHeader } from '@/components/shell/PageHeader'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Panel } from '@/components/ui/Card'
import { MetricTile, MetricTiles, TileGrid } from '@/components/ui/MetricTile'
import { sameRequest } from '@/lib/equal'
import {
  formatCurrency,
  formatDateRange,
  formatMetric,
  formatMetricDelta,
  formatNumber,
  formatPercent,
  isNum,
  METRIC_LABELS,
  deltaTone,
  formatPercentTick,
} from '@/lib/format'
import { hasColumn } from '@/lib/series'
import { cleanTicker, marketIssues } from '@/state/defaults'
import { useMarket } from '@/state/market'
import { DEFAULT_BACKTEST_FORM, type BacktestForm } from '@/state/forms'
import { usePageState } from '@/state/store'
import { useChartColors } from '@/theme/chart'
import { defaultParameters, findStrategy, parameterIssues, parametersEqual } from '@/lib/meta'

export default function BacktestPage() {
  return (
    <>
      <PageHeader
        title="Backtest"
        description="Study one strategy in depth: its signals on the price chart, exposure, equity and drawdown against Buy and Hold, under your cost and cash assumptions."
      />
      <PageBody>
        <WithMeta>{(meta) => <Backtest meta={meta} />}</WithMeta>
      </PageBody>
    </>
  )
}

function Backtest({ meta }: { meta: Meta }) {
  const [market, setMarket] = useMarket()
  const [form, setForm] = usePageState<BacktestForm>('backtest:form', DEFAULT_BACKTEST_FORM)
  const run = useBacktestRun()
  const strategy = findStrategy(meta, form.strategy)
  const defaults = defaultParameters(strategy)
  const parameters = { ...defaults, ...form.parameters[strategy.key] }

  const request: BacktestRequest = {
    ...market,
    ticker: cleanTicker(market.ticker),
    strategy: strategy.key,
    parameters,
  }
  const issues = [...marketIssues(market), ...parameterIssues(strategy.key, parameters)]
  const stale = run.request !== null && !sameRequest(request, run.request)
  const submit = () => run.run(request)
  const isDefault = parametersEqual(parameters, defaults)

  return (
    <ResearchLayout
      panel={
        <ControlPanel onRun={submit} running={run.running} issues={issues} runLabel="Run backtest">
          <FieldGroup title="Strategy">
            <StrategySelect
              meta={meta}
              value={strategy.key}
              onChange={(key) => setForm({ ...form, strategy: key })}
            />
          </FieldGroup>
          <FieldGroup title="Parameters">
            <ParameterFields
              strategy={strategy}
              values={parameters}
              onChange={(values) =>
                setForm({ ...form, parameters: { ...form.parameters, [strategy.key]: values } })
              }
            />
            {!isDefault && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  setForm({ ...form, parameters: { ...form.parameters, [strategy.key]: defaults } })
                }
              >
                Reset to defaults
              </Button>
            )}
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
        runningText="Downloading prices and running the backtest…"
        empty={
          <EmptyState title="Backtest a strategy">
            Choose a strategy and its parameters, then run. A signal computed on day t sets the
            position for day t+1; costs apply to every change in exposure.
          </EmptyState>
        }
      >
        {run.data && run.request && (
          <BacktestResults data={run.data} request={run.request} meta={meta} />
        )}
      </ResultsArea>
    </ResearchLayout>
  )
}

function BacktestResults({
  data,
  request,
  meta,
}: {
  data: BacktestResponse
  request: BacktestRequest
  meta: Meta
}) {
  const c = useChartColors()
  const strategy = findStrategy(meta, data.strategy)
  const { series } = data
  const defaults = defaultParameters(strategy)

  const strategyName =
    meta.strategies.find((s) => s.key === data.strategy)?.display_name ?? data.strategy
  const equityOption = useMemo(
    () =>
      timeLines(c, {
        dates: series.dates,
        lines: [
          {
            name: strategyName,
            values: series.columns.strategy_equity,
            color: c.series[0],
          },
          { name: 'Buy and Hold', values: series.columns.buy_hold_equity, color: c.reference },
        ],
        format: (v) => formatCurrency(v),
        axisFormat: (v) => formatCurrency(v, { compact: true }),
        reference: { value: request.initial_capital ?? 10_000 },
      }),
    [c, series, strategyName, request.initial_capital],
  )

  const drawdownOption = useMemo(
    () =>
      timeLines(c, {
        dates: series.dates,
        lines: [
          {
            name: strategyName,
            values: series.columns.strategy_drawdown,
            color: c.series[0],
            area: true,
          },
          { name: 'Buy and Hold', values: series.columns.buy_hold_drawdown, color: c.reference },
        ],
        format: (v) => formatPercent(v),
        axisFormat: formatPercentTick,
        maxZero: true,
      }),
    [c, series, strategyName],
  )

  const hasOscillators = Object.values(data.oscillators.columns).some((col) => col.some(isNum))
  const priceOption = useMemo(
    () =>
      priceChart(c, {
        dates: series.dates,
        close: series.columns.close,
        position: series.columns.position,
        overlays: data.overlays,
        oscillators: hasOscillators ? data.oscillators : null,
        thresholds: Object.entries(data.parameters)
          .filter(([key]) => key.endsWith('_threshold'))
          .map(([key, value]) => ({ value, label: key.replace('_threshold', '') })),
      }),
    [c, series, data.overlays, data.oscillators, data.parameters, hasOscillators],
  )

  const exposureOption = useMemo(
    () =>
      timeLines(c, {
        dates: series.dates,
        lines: [
          {
            name: 'Exposure',
            values: series.columns.position,
            color: c.series[0],
            area: true,
            step: true,
          },
        ],
        format: (v) => formatPercent(v, 0),
        showLegend: false,
      }),
    [c, series],
  )
  const fractional = series.columns.position?.some((v) => isNum(v) && v > 0 && v < 1) ?? false

  const extraKeys: Array<keyof Metrics> = [
    'final_value',
    'average_exposure',
    'turnover',
    'rebalancing_days',
  ]

  return (
    <>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
          <span className="font-semibold text-ink">{strategy.display_name}</span>
          <span className="font-mono font-medium text-ink">{request.ticker}</span>
          <span>{formatDateRange(request.start_date, request.end_date)}</span>
        </div>
        {parametersEqual(data.parameters, defaults) ? (
          <Badge>Default parameters</Badge>
        ) : (
          <Badge tone="accent" title="Parameters differ from the registry defaults">
            Custom parameters
          </Badge>
        )}
      </div>
      <ParamChips parameters={data.parameters} specs={strategy.parameters} baseline={defaults} />

      <MetricTiles metrics={data.metrics} reference={data.benchmark_metrics} />
      <TileGrid className="sm:grid-cols-4 2xl:grid-cols-4">
        {extraKeys.map((key) => {
          const value = data.metrics[key]
          const ref = data.benchmark_metrics[key]
          const delta = key === 'final_value' && isNum(value) && isNum(ref) ? value - ref : null
          return (
            <MetricTile
              key={key}
              label={METRIC_LABELS[key]}
              value={formatMetric(key, value)}
              delta={key === 'final_value' ? formatMetricDelta(key, delta) : undefined}
              deltaTone={deltaTone(key, delta)}
              deltaLabel={key === 'final_value' ? 'vs B&H' : undefined}
              hint={
                key === 'turnover'
                  ? 'one-way, × capital'
                  : key === 'average_exposure'
                    ? 'share of capital invested'
                    : key === 'rebalancing_days'
                      ? 'days exposure changed'
                      : undefined
              }
            />
          )
        })}
      </TileGrid>

      <Panel
        title="Portfolio value"
        description="Strategy equity against Buy and Hold from the same starting capital."
      >
        <EChart
          option={equityOption}
          height={320}
          ariaLabel="Strategy and Buy and Hold portfolio value over time"
        />
      </Panel>

      <Panel title="Drawdown" description="Decline from the running peak.">
        <EChart
          option={drawdownOption}
          height={220}
          ariaLabel="Strategy and Buy and Hold drawdown over time"
        />
      </Panel>

      <Panel
        title="Price and signals"
        description={
          <>
            Close price with the strategy's indicators. Shaded periods hold a position
            {hasOscillators ? '; oscillators are in the lower panel on their own scale.' : '.'}
          </>
        }
      >
        <EChart
          option={priceOption}
          height={hasOscillators ? 460 : 340}
          ariaLabel="Price chart with indicator overlays and position shading"
        />
      </Panel>

      {hasColumn(series, 'position') && fractional && (
        <Panel
          title="Exposure"
          description="Fraction of capital invested each day (position sizing is continuous)."
        >
          <EChart option={exposureOption} height={180} ariaLabel="Daily exposure" />
        </Panel>
      )}

      <Panel title="Strategy vs Buy and Hold" description="Every metric side by side.">
        <ComparisonTable metrics={data.metrics} benchmark={data.benchmark_metrics} />
      </Panel>
    </>
  )
}

function ComparisonTable({ metrics, benchmark }: { metrics: Metrics; benchmark: Metrics }) {
  const keys = Object.keys(METRIC_LABELS).filter(
    (key) => key in metrics || key in benchmark,
  ) as Array<keyof Metrics>
  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full text-[13px]">
        <caption className="sr-only">Strategy and Buy and Hold metrics</caption>
        <thead>
          <tr className="bg-surface-2 text-xs text-muted">
            <th scope="col" className="px-3 py-2 text-left font-medium">
              Metric
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Strategy
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Buy and Hold
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Difference
            </th>
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => {
            const a = metrics[key]
            const b = benchmark[key]
            const delta = isNum(a) && isNum(b) ? a - b : null
            const tone = deltaTone(key, delta)
            return (
              <tr key={key} className="border-t border-line">
                <th scope="row" className="px-3 py-1.5 text-left font-normal text-ink-2">
                  {METRIC_LABELS[key]}
                </th>
                <td className="num px-3 py-1.5 text-right font-mono text-[12px]">
                  {formatMetric(key, a)}
                </td>
                <td className="num px-3 py-1.5 text-right font-mono text-[12px] text-ink-2">
                  {formatMetric(key, b)}
                </td>
                <td
                  className={`num px-3 py-1.5 text-right font-mono text-[12px] ${tone === 'pos' ? 'text-pos' : tone === 'neg' ? 'text-neg' : 'text-muted'}`}
                >
                  {key === 'rebalancing_days' || key === 'turnover' || key === 'average_exposure'
                    ? key === 'average_exposure'
                      ? formatMetricDelta(key, delta)
                      : formatNumber(delta, key === 'turnover' ? 1 : 0)
                    : formatMetricDelta(key, delta)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
