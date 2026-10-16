import clsx from 'clsx'
import type { ParameterSpec, Parameters } from '@/api/types'
import { formatParameterValue, humanize } from '@/lib/format'

/** Parameters as compact label/value chips; values that differ from `baseline` are emphasized. */
export function ParamChips({
  parameters,
  specs,
  baseline,
  className,
}: {
  parameters: Parameters
  specs?: Record<string, ParameterSpec>
  baseline?: Parameters
  className?: string
}) {
  const entries = Object.entries(parameters)
  if (!entries.length) return <span className="text-xs text-muted">No parameters</span>
  return (
    <ul className={clsx('flex flex-wrap gap-1.5', className)}>
      {entries.map(([key, value]) => {
        const changed =
          baseline !== undefined && baseline[key] !== undefined && baseline[key] !== value
        return (
          <li
            key={key}
            className={clsx(
              'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs',
              changed ? 'border-accent-line bg-accent-soft' : 'border-line bg-surface-2',
            )}
            title={specs?.[key]?.label}
          >
            <span className="text-muted">{shortLabel(key, specs?.[key]?.label)}</span>
            <span className="num font-mono font-medium text-ink">
              {formatParameterValue(value, specs?.[key])}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function shortLabel(key: string, label?: string): string {
  if (label && label.length <= 22) return label
  return humanize(key)
}
