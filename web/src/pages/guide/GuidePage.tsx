import clsx from 'clsx'
import { Link } from 'react-router'
import type { Meta } from '@/api/types'
import { WithMeta } from '@/components/controls/StrategyFields'
import { PageBody, PageHeader } from '@/components/shell/PageHeader'
import { Icon } from '@/components/ui/Icon'
import { usePageState } from '@/state/store'

export default function GuidePage() {
  return (
    <>
      <PageHeader
        title="Strategy guide"
        description="The ideas behind each rule: what market behavior it is built around, where it should work, where it should struggle, and what to watch when optimizing and validating it."
      />
      <PageBody>
        <WithMeta>{(meta) => <Guide meta={meta} />}</WithMeta>
      </PageBody>
    </>
  )
}

function Guide({ meta }: { meta: Meta }) {
  const [query, setQuery] = usePageState('guide:query', '')
  const [family, setFamily] = usePageState('guide:family', 'All')
  const families = ['All', ...new Set(meta.strategies.map((s) => s.family))]
  const q = query.trim().toLowerCase()
  const matches = meta.strategies.filter(
    (s) =>
      (family === 'All' || s.family === family) &&
      (!q ||
        [s.display_name, s.family, s.subtype, s.description, s.thesis, ...s.features]
          .join(' ')
          .toLowerCase()
          .includes(q)),
  )
  const grouped = families
    .filter((f) => f !== 'All')
    .map((f) => ({ family: f, items: matches.filter((s) => s.family === f) }))
    .filter((g) => g.items.length)

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <label htmlFor="guide-search" className="sr-only">
            Search strategies
          </label>
          <Icon
            name="search"
            className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted"
          />
          <input
            id="guide-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search strategies, features…"
            className="h-9 w-full rounded-lg border border-line-strong bg-surface pr-3 pl-9 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none"
          />
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by family">
          {families.map((f) => (
            <button
              key={f}
              type="button"
              aria-pressed={family === f}
              onClick={() => setFamily(f)}
              className={clsx(
                'h-8 rounded-full border px-3 text-xs font-medium transition-colors',
                family === f
                  ? 'border-accent-line bg-accent-soft text-ink'
                  : 'border-line text-muted hover:text-ink',
              )}
            >
              {f}
              {f !== 'All' && (
                <span className="ml-1.5 text-muted">
                  {meta.strategies.filter((s) => s.family === f).length}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {grouped.length === 0 && (
        <p className="py-12 text-center text-sm text-muted">No strategy matches “{query}”.</p>
      )}

      {grouped.map((group) => (
        <section key={group.family} aria-labelledby={`fam-${group.family}`}>
          <h2
            id={`fam-${group.family}`}
            className="mb-3 text-[11px] font-semibold tracking-wider text-muted uppercase"
          >
            {group.family}
          </h2>
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {group.items.map((s) => (
              <li key={s.key}>
                <Link
                  to={`/guide/${s.key}`}
                  className="group flex h-full flex-col rounded-xl border border-line bg-surface p-4 shadow-card transition-colors hover:border-accent-line"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="text-[15px] font-semibold text-ink">{s.display_name}</h3>
                      <p className="text-xs text-muted">{s.subtype}</p>
                    </div>
                    <Icon
                      name="arrowRight"
                      className="mt-1 shrink-0 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent"
                    />
                  </div>
                  <p className="mt-2 text-[13px] leading-relaxed text-ink-2">{s.description}</p>
                  <p className="mt-auto pt-3 text-xs text-muted">
                    <span className="text-ink-2">Best for:</span> {s.best_suited_for}
                  </p>
                  <ul className="mt-2 flex flex-wrap gap-1">
                    {s.features.map((f) => (
                      <li
                        key={f}
                        className="rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] text-ink-2"
                      >
                        {f}
                      </li>
                    ))}
                  </ul>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
