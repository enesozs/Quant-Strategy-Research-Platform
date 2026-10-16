import clsx from 'clsx'
import type { ReactNode } from 'react'
import { Icon } from './Icon'

type AlertTone = 'error' | 'warn' | 'info'

const TONES: Record<AlertTone, string> = {
  error: 'border-neg/35 bg-neg-soft text-ink',
  warn: 'border-warn/35 bg-warn-soft text-ink',
  info: 'border-line bg-surface-2 text-ink-2',
}

export function Alert({
  tone = 'info',
  title,
  children,
  action,
  className,
}: {
  tone?: AlertTone
  title?: ReactNode
  children?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={clsx(
        'flex items-start gap-3 rounded-lg border px-3.5 py-2.5 text-[13px]',
        TONES[tone],
        className,
      )}
    >
      <Icon
        name={tone === 'info' ? 'info' : 'alert'}
        className={clsx(
          'mt-0.5 shrink-0',
          tone === 'error' ? 'text-neg' : tone === 'warn' ? 'text-warn' : 'text-muted',
        )}
      />
      <div className="min-w-0 flex-1 leading-relaxed">
        {title && <p className="font-medium text-ink">{title}</p>}
        {children && <div className={clsx(title && 'mt-0.5', 'break-words')}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
