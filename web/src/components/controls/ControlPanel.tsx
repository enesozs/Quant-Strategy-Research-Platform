// Layout and run feedback shared by every research page. On desktop the settings panel is
// rendered into the sidebar (below the navigation) so results use the full page width; on
// narrow screens it is stacked above the results. The results column keeps the last result
// visible while a new run is in flight or after settings change.

import clsx from 'clsx'
import { useEffect, useId, useState, type FormEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { ResultsSkeleton } from '@/components/ui/Skeleton'
import { formatElapsed } from '@/lib/format'
import {
  InSidebarContext,
  useInSidebar,
  useIsDesktop,
  useSidebarSlot,
} from '@/components/shell/sidebarSlot'

export function ResearchLayout({ panel, children }: { panel: ReactNode; children: ReactNode }) {
  const slot = useSidebarSlot()
  const desktop = useIsDesktop()

  if (desktop && slot)
    return (
      <>
        {createPortal(
          <InSidebarContext.Provider value={true}>{panel}</InSidebarContext.Provider>,
          slot,
        )}
        <div id="results" className="min-w-0 scroll-mt-20">
          {children}
        </div>
      </>
    )

  return (
    <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[320px_minmax(0,1fr)]">
      <div className="min-w-0 lg:sticky lg:top-6 lg:self-start">{panel}</div>
      <div id="results" className="min-w-0 scroll-mt-20">
        {children}
      </div>
    </div>
  )
}

export function ControlPanel({
  title = 'Settings',
  children,
  onRun,
  running,
  runLabel = 'Run',
  issues = [],
  secondary,
}: {
  title?: string
  children: ReactNode
  onRun: () => void
  running: boolean
  runLabel?: string
  /** Blocking input problems; Run is disabled while any exist. */
  issues?: string[]
  /** Extra actions under the Run button. */
  secondary?: ReactNode
}) {
  const headingId = useId()
  const inSidebar = useInSidebar()
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (running || issues.length > 0) return
    onRun()
    // Stacked layout: bring the results (and the loading state) into view.
    if (window.matchMedia?.('(max-width: 1023px)').matches)
      document.getElementById('results')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  return (
    <form
      onSubmit={submit}
      aria-labelledby={headingId}
      className={clsx(
        'flex flex-col',
        inSidebar
          ? 'min-h-0 flex-1 border-t border-line'
          : 'rounded-xl border border-line bg-surface shadow-card lg:max-h-[calc(100dvh-3rem)]',
      )}
    >
      <div
        className={clsx(
          'flex items-center justify-between',
          inSidebar ? 'px-1.5 pt-2.5' : 'border-b border-line px-4 py-3',
        )}
      >
        <h2
          id={headingId}
          className={clsx(
            inSidebar
              ? 'text-[11px] font-semibold tracking-wider text-muted uppercase'
              : 'text-sm font-semibold text-ink',
          )}
        >
          {title}
        </h2>
      </div>
      <div
        className={clsx(
          'scrollbar-thin scroll-fade min-h-0 flex-1 space-y-1 overflow-y-auto py-2',
          inSidebar ? 'px-1.5' : 'px-4',
        )}
      >
        {children}
      </div>
      <div
        className={clsx('space-y-2 border-t border-line', inSidebar ? 'px-1.5 pt-3 pb-3' : 'p-4')}
      >
        {issues.length > 0 && (
          <ul className="space-y-0.5 text-xs text-neg" aria-live="polite">
            {issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        )}
        <Button
          type="submit"
          variant="primary"
          className="w-full"
          disabled={running || issues.length > 0}
          aria-busy={running}
        >
          {running ? <Spinner /> : <Icon name="play" size={14} />}
          {running ? 'Running…' : runLabel}
        </Button>
        {secondary}
      </div>
    </form>
  )
}

/** A titled group of fields inside the control panel; optionally collapsible. */
export function FieldGroup({
  title,
  children,
  collapsible,
  defaultOpen = true,
  summary,
}: {
  title: string
  children: ReactNode
  collapsible?: boolean
  defaultOpen?: boolean
  summary?: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  const bodyId = useId()
  if (!collapsible)
    return (
      <div
        role="group"
        aria-labelledby={bodyId}
        className="space-y-3 border-b border-line py-3 last:border-b-0"
      >
        <p id={bodyId} className="text-[11px] font-semibold tracking-wider text-muted uppercase">
          {title}
        </p>
        {children}
      </div>
    )
  return (
    <div className="border-b border-line py-3 last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <span className="min-w-0">
          <span className="block text-[11px] font-semibold tracking-wider text-muted uppercase">
            {title}
          </span>
          {!open && summary && (
            <span className="num mt-0.5 block truncate text-xs text-ink-2">{summary}</span>
          )}
        </span>
        <Icon name={open ? 'chevronUp' : 'chevronDown'} className="shrink-0 text-muted" />
      </button>
      <fieldset id={bodyId} hidden={!open} className="mt-3 space-y-3">
        <legend className="sr-only">{title}</legend>
        {children}
      </fieldset>
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={clsx('size-3.5 animate-spin', className)}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2" />
      <path d="M14 8a6 6 0 0 0-6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  return <span className="num">{formatElapsed(now - since)}</span>
}

/**
 * The results column: error alert, running bar, stale banner, then either the last result
 * (dimmed while a new run is in flight), a skeleton on the first run, or an empty state.
 */
export function ResultsArea({
  hasData,
  running,
  startedAt,
  error,
  stale,
  onRerun,
  runningText = 'Running research — downloading prices and computing results.',
  empty,
  skeleton,
  children,
}: {
  hasData: boolean
  running: boolean
  startedAt: number | null
  error: string | null
  stale: boolean
  onRerun?: () => void
  runningText?: string
  empty: ReactNode
  skeleton?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="space-y-4">
      {error && !running && (
        <Alert tone="error" title="The run failed">
          {error}
        </Alert>
      )}
      {running && (
        <div
          role="status"
          className="relative overflow-hidden rounded-lg border border-accent-line bg-accent-soft px-3.5 py-2.5 text-[13px] text-ink"
        >
          <div className="flex items-center gap-2.5">
            <Spinner className="text-accent" />
            <span className="min-w-0 flex-1">{runningText}</span>
            {startedAt && <Elapsed since={startedAt} />}
          </div>
          <div className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden">
            <div className="animate-progress h-full w-2/5 bg-accent" />
          </div>
        </div>
      )}
      {stale && !running && hasData && (
        <Alert
          tone="warn"
          title="Settings changed"
          action={
            onRerun && (
              <Button size="sm" variant="secondary" onClick={onRerun}>
                <Icon name="refresh" size={13} />
                Re-run
              </Button>
            )
          }
        >
          These results reflect the previous run. Re-run to refresh them.
        </Alert>
      )}
      {hasData ? (
        <div
          className={clsx(
            'space-y-4 transition-opacity',
            running && 'pointer-events-none opacity-55',
          )}
          aria-busy={running}
        >
          {children}
        </div>
      ) : running ? (
        (skeleton ?? <ResultsSkeleton />)
      ) : (
        empty
      )}
    </div>
  )
}

export function EmptyState({
  title,
  children,
  icon = 'flask',
}: {
  title: string
  children: ReactNode
  icon?: 'flask'
}) {
  return (
    <div className="flex min-h-[320px] flex-col items-center justify-center rounded-xl border border-dashed border-line-strong bg-surface/50 px-6 py-12 text-center">
      <span className="grid size-10 place-items-center rounded-full bg-accent-soft text-accent">
        <Icon name={icon} size={18} />
      </span>
      <h2 className="mt-3 text-[15px] font-semibold text-ink">{title}</h2>
      <div className="mt-1 max-w-md text-sm leading-relaxed text-muted">{children}</div>
    </div>
  )
}
