import { useNavigate } from 'react-router'
import { usePairsDiscoverRun } from '@/api/client'
import type { Meta, PairsDiscoverResponse, PairsUniverseRequest, Row } from '@/api/types'
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
import { DataTable, type Column } from '@/components/ui/DataTable'
import { sameRequest } from '@/lib/equal'
import { formatDate, formatDateRange, formatPValue, humanize, isNum } from '@/lib/format'
import { usePairsAssumptions } from '@/state/market'
import { MethodField, MethodParamFields } from './PairsControls'
import { paramIssues, universeParams, currentParams } from './params'
import { parseTickers, usePairsForm, useUniverseForm, universeIssues } from './state'
import { UniverseFields } from './UniverseFields'
import { marketIssues } from '@/state/defaults'

export default function DiscoverPage() {
  return <WithMeta>{(meta) => <Discover meta={meta} />}</WithMeta>
}

function Discover({ meta }: { meta: Meta }) {
  const [assumptions, setAssumptions] = usePairsAssumptions()
  const [form, setForm] = usePairsForm()
  const [universe, setUniverse] = useUniverseForm()
  const run = usePairsDiscoverRun()
  const navigate = useNavigate()
  const params = currentParams(form)

  const request: PairsUniverseRequest = {
    ...assumptions,
    method: form.method,
    tickers: parseTickers(universe.tickers),
    formation_years: universe.formation_years,
    top_n: universe.discover_top_n,
    params: universeParams(params),
  }
  const issues = [...marketIssues(assumptions), ...universeIssues(universe), ...paramIssues(params)]
  const stale = run.request !== null && !sameRequest(request, run.request)
  const submit = () => run.run(request)

  const research = (row: Row) => {
    setForm((f) => ({ ...f, ticker_a: String(row.asset_a), ticker_b: String(row.asset_b) }))
    navigate('/pairs')
  }

  return (
    <ResearchLayout
      panel={
        <ControlPanel
          onRun={submit}
          running={run.running}
          issues={issues}
          runLabel="Discover pairs"
        >
          <UniverseFields
            meta={meta}
            universe={universe}
            setUniverse={setUniverse}
            topNKey="discover_top_n"
          />
          <FieldGroup title="Model">
            <MethodField meta={meta} form={form} setForm={setForm} />
          </FieldGroup>
          {form.method !== 'distance' && (
            <MethodParamFields
              form={form}
              setForm={setForm}
              hide={[
                'formation_years',
                'trading_months',
                'entry_zscore',
                'exit_zscore',
                'stop_zscore',
                'maximum_holding_days',
                'require_qualification',
                'adf_reference_pvalue',
              ]}
              collapsed
            />
          )}
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
        runningText="Downloading the universe and ranking every pair on the selection window…"
        empty={
          <EmptyState title="Rank candidate pairs">
            Every pair in the universe is ranked on the opening selection window only, so the later
            period stays out of sample for the selection step.
          </EmptyState>
        }
      >
        {run.data && run.request && (
          <DiscoverResults data={run.data} request={run.request} onResearch={research} />
        )}
      </ResultsArea>
    </ResearchLayout>
  )
}

function DiscoverResults({
  data,
  request,
  onResearch,
}: {
  data: PairsDiscoverResponse
  request: PairsUniverseRequest
  onResearch: (row: Row) => void
}) {
  const hasBonferroni = data.rows.some((row) => 'bonferroni_pvalue' in row)
  const keys = [...new Set(data.rows.flatMap((row) => Object.keys(row)))]
  const columns: Column[] = [
    {
      key: 'pair',
      label: 'Pair',
      render: (row) => (
        <span className="font-mono text-[12px] font-medium text-ink">
          {String(row.asset_a)} / {String(row.asset_b)}
        </span>
      ),
      sortValue: (row) => `${row.asset_a}/${row.asset_b}`,
    },
    // The Bonferroni p-value leads, so it is never scrolled out of view.
    ...[
      ...keys.filter((key) => key === 'bonferroni_pvalue'),
      ...keys.filter((key) => key !== 'bonferroni_pvalue'),
    ]
      .filter((key) => key !== 'asset_a' && key !== 'asset_b')
      .map<Column>((key) =>
        key === 'bonferroni_pvalue'
          ? {
              key,
              highlight: true,
              title: 'p-value × number of pairs tested: controls for testing many pairs at once',
              render: (row) => (
                <span className={isNum(row[key]) && row[key] <= 0.1 ? 'text-pos' : undefined}>
                  {formatPValue(row[key])}
                </span>
              ),
            }
          : key === 'qualified'
            ? {
                key,
                render: (row) => (row[key] ? <Badge tone="pos">Yes</Badge> : <Badge>No</Badge>),
              }
            : { key },
      ),
  ]
  const universe = request.tickers.length
  const tested = (universe * (universe - 1)) / 2

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <Badge>{humanize(request.method)}</Badge>
        <span>
          {universe} tickers · {tested} candidate pairs · top {data.rows.length}
        </span>
      </div>
      <Alert
        tone="info"
        title={`Selection window: ${formatDateRange(data.selection_start, data.selection_end)}`}
      >
        Pairs are ranked using only this opening window, so anything after{' '}
        {formatDate(data.selection_end)} is out of sample for the selection step. Research or trade
        them from there.
      </Alert>
      {hasBonferroni && (
        <Alert tone="warn" title="Read the Bonferroni column">
          With {tested} pairs tested, about {Math.max(1, Math.round(tested * 0.1))} would look
          cointegrated at the 10% level by chance alone. The Bonferroni p-value multiplies each
          p-value by the number of pairs; a good rank marks a pair worth researching, not a proven
          relationship.
        </Alert>
      )}
      <Panel
        title="Candidate pairs"
        description="Ranked best first. Select a row to research that pair."
      >
        <DataTable
          caption="Discovered pairs"
          rows={data.rows}
          columns={columns}
          onRowClick={onResearch}
          rowActionLabel={(row) => `Research ${row.asset_a} / ${row.asset_b}`}
          emptyText="No pair passed the filters in the selection window."
        />
      </Panel>
    </>
  )
}
