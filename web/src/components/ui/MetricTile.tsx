import clsx from 'clsx'
import type { ReactNode } from 'react'
import type { Metrics } from '@/api/types'
import {
  deltaTone,
  type DeltaTone,
  formatMetric,
  formatMetricDelta,
  isNum,
  METRIC_LABELS,
} from '@/lib/format'

export function MetricTile({
  label,
  value,
  delta,
  deltaTone = 'neutral',
  deltaLabel,
  hint,
  emphasis,
  className,
}: {
  label: ReactNode
  value: ReactNode
  delta?: ReactNode
  deltaTone?: DeltaTone
  deltaLabel?: ReactNode
  hint?: ReactNode
  emphasis?: boolean
  className?: string
}) {
  return (
    <div
      className={clsx(
        'min-w-0 rounded-xl border bg-surface px-4 py-3 shadow-card',
        emphasis ? 'border-accent-line' : 'border-line',
        className,
      )}
    >
      <dt className="truncate text-xs font-medium text-muted">{label}</dt>
      <dd className="mt-1">
        <span className="num block truncate text-[22px] leading-7 font-semibold tracking-tight text-ink">
          {value}
        </span>
        {(delta || hint) && (
          <span className="mt-0.5 flex min-w-0 items-baseline gap-1.5 text-xs">
            {delta && (
              <span
                className={clsx(
                  'num font-medium whitespace-nowrap',
                  deltaTone === 'pos'
                    ? 'text-pos'
                    : deltaTone === 'neg'
                      ? 'text-neg'
                      : 'text-ink-2',
                )}
              >
                {delta}
              </span>
            )}
            {deltaLabel && <span className="truncate text-muted">{deltaLabel}</span>}
            {!delta && hint && <span className="truncate text-muted">{hint}</span>}
          </span>
        )}
      </dd>
    </div>
  )
}

export function TileGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <dl className={clsx('grid grid-cols-2 gap-3 sm:grid-cols-3 2xl:grid-cols-6', className)}>
      {children}
    </dl>
  )
}

/** Standard metric tiles with a delta vs a reference (Buy and Hold, defaults, ...). */
export function MetricTiles({
  metrics,
  reference,
  referenceLabel = 'vs B&H',
  keys = [
    'total_return',
    'cagr',
    'sharpe_ratio',
    'max_drawdown',
    'annualized_volatility',
    'calmar_ratio',
  ],
  className,
}: {
  metrics: Metrics
  reference?: Metrics
  referenceLabel?: string
  keys?: Array<keyof Metrics>
  className?: string
}) {
  return (
    <TileGrid className={className}>
      {keys.map((key) => {
        const value = metrics[key]
        const ref = reference?.[key]
        const delta = isNum(value) && isNum(ref) ? value - ref : null
        return (
          <MetricTile
            key={key}
            label={METRIC_LABELS[key] ?? key}
            value={formatMetric(key, value)}
            delta={reference ? formatMetricDelta(key, delta) : undefined}
            deltaTone={deltaTone(key, delta)}
            deltaLabel={reference ? referenceLabel : undefined}
          />
        )
      })}
    </TileGrid>
  )
}
