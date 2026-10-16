import type { ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import type { Meta } from '@/api/types'
import { WithMeta } from '@/components/controls/StrategyFields'
import { PageBody } from '@/components/shell/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Icon } from '@/components/ui/Icon'
import { formatInteger, formatParameterValue } from '@/lib/format'
import { selectStrategy } from '@/state/forms'

export default function StrategyDetailPage() {
  return (
    <PageBody>
      <WithMeta>{(meta) => <Detail meta={meta} />}</WithMeta>
    </PageBody>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="text-[11px] font-semibold tracking-wider text-muted uppercase">{title}</h2>
      <div className="mt-1.5 text-sm leading-relaxed text-ink-2">{children}</div>
    </section>
  )
}

function Detail({ meta }: { meta: Meta }) {
  const { key } = useParams()
  const navigate = useNavigate()
  const strategy = meta.strategies.find((s) => s.key === key)
  if (!strategy)
    return (
      <Alert
        tone="error"
        title="Unknown strategy"
        action={
          <Link className="text-accent" to="/guide">
            Back to guide
          </Link>
        }
      >
        No strategy is registered as “{key}”.
      </Alert>
    )

  const related = strategy.related_strategies.map(
    (name) =>
      meta.strategies.find((s) => s.display_name === name) ?? { display_name: name, key: null },
  )

  const open = (path: string, storeKey: 'backtest:form' | 'optimize:form' | 'validate:form') => {
    selectStrategy(storeKey, strategy.key)
    navigate(path)
  }

  return (
    <article className="mx-auto max-w-5xl space-y-6">
      <Link
        to="/guide"
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"
      >
        <Icon name="arrowLeft" size={14} />
        All strategies
      </Link>

      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="accent">{strategy.family}</Badge>
          <Badge>{strategy.subtype}</Badge>
          <Badge>{strategy.signal_style}</Badge>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{strategy.display_name}</h1>
        <p className="max-w-3xl text-[15px] leading-relaxed text-ink-2">{strategy.description}</p>
        <div className="flex flex-wrap gap-2 pt-2">
          <Button variant="primary" size="sm" onClick={() => open('/backtest', 'backtest:form')}>
            Backtest it
          </Button>
          <Button size="sm" onClick={() => open('/optimize', 'optimize:form')}>
            Optimize
          </Button>
          <Button size="sm" onClick={() => open('/validate', 'validate:form')}>
            Validate
          </Button>
        </div>
      </header>

      <Card className="p-5">
        <Section title="Thesis">
          <p className="text-[15px] text-ink">{strategy.thesis}</p>
        </Section>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="p-5">
          <Section title="Favorable environment">{strategy.favorable_environment}</Section>
        </Card>
        <Card className="p-5">
          <Section title="Unfavorable environment">{strategy.unfavorable_environment}</Section>
        </Card>
        <Card className="p-5">
          <Section title="Main risks">{strategy.main_risks}</Section>
        </Card>
        <Card className="p-5">
          <Section title="Best suited for">{strategy.best_suited_for}</Section>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <div className="px-5 pt-5">
          <h2 className="text-[11px] font-semibold tracking-wider text-muted uppercase">
            Parameters
          </h2>
          <p className="mt-1 text-xs text-muted">
            Predefined optimization grid: {formatInteger(strategy.grid_size)} combinations.
          </p>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-[13px]">
            <caption className="sr-only">Parameters of {strategy.display_name}</caption>
            <thead>
              <tr className="border-y border-line bg-surface-2 text-xs text-muted">
                <th scope="col" className="px-5 py-2 text-left font-medium">
                  Parameter
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Default
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Range
                </th>
                <th scope="col" className="px-5 py-2 text-left font-medium">
                  Research grid
                </th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(strategy.parameters).map(([name, spec]) => (
                <tr key={name} className="border-b border-line last:border-b-0">
                  <th scope="row" className="px-5 py-2 text-left font-normal">
                    <span className="text-ink">{spec.label}</span>
                    <span className="block font-mono text-[11px] text-muted">{name}</span>
                  </th>
                  <td className="num px-3 py-2 text-right font-mono text-[12px] text-ink">
                    {formatParameterValue(spec.default, spec)}
                  </td>
                  <td className="num px-3 py-2 text-right font-mono text-[12px] whitespace-nowrap text-ink-2">
                    {formatParameterValue(spec.min, spec)}–{formatParameterValue(spec.max, spec)}
                  </td>
                  <td className="num px-5 py-2 font-mono text-[12px] text-ink-2">
                    {(strategy.default_grid[name] ?? [])
                      .map((v) => formatParameterValue(v, spec))
                      .join(', ') || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="p-5">
          <Section title="Optimization notes">{strategy.optimization_notes}</Section>
        </Card>
        <Card className="p-5">
          <Section title="Validation focus">{strategy.validation_focus}</Section>
        </Card>
      </div>

      {related.length > 0 && (
        <Section title="Related strategies">
          <ul className="flex flex-wrap gap-2">
            {related.map((r) => (
              <li key={r.display_name}>
                {r.key ? (
                  <Link
                    to={`/guide/${r.key}`}
                    className="inline-flex h-8 items-center rounded-full border border-line px-3 text-xs font-medium text-ink-2 hover:border-accent-line hover:text-ink"
                  >
                    {r.display_name}
                  </Link>
                ) : (
                  <span className="inline-flex h-8 items-center rounded-full border border-line px-3 text-xs text-muted">
                    {r.display_name}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </article>
  )
}
