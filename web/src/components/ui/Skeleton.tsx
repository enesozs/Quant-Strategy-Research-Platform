import clsx from 'clsx'

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={clsx(
        'animate-shimmer rounded-md bg-[linear-gradient(90deg,var(--surface-2)_25%,var(--surface-3)_50%,var(--surface-2)_75%)] bg-[length:200%_100%]',
        className,
      )}
    />
  )
}

/** Placeholder for a results column on the first run: tiles, a chart and a table. */
export function ResultsSkeleton({ tiles = 6, charts = 2 }: { tiles?: number; charts?: number }) {
  return (
    <div className="space-y-4" aria-hidden="true">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: tiles }, (_, i) => (
          <div key={i} className="rounded-xl border border-line bg-surface p-4">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="mt-3 h-6 w-20" />
            <Skeleton className="mt-2 h-3 w-12" />
          </div>
        ))}
      </div>
      {Array.from({ length: charts }, (_, i) => (
        <div key={i} className="rounded-xl border border-line bg-surface p-5">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="mt-4 h-56 w-full" />
        </div>
      ))}
    </div>
  )
}
