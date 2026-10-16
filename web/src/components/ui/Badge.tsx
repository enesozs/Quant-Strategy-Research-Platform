import clsx from 'clsx'
import type { ReactNode } from 'react'

export type Tone = 'neutral' | 'accent' | 'warn' | 'pos' | 'neg'

const TONES: Record<Tone, string> = {
  neutral: 'bg-surface-2 text-ink-2 border-line',
  accent: 'bg-accent-soft text-accent border-accent-line',
  warn: 'bg-warn-soft text-warn border-warn/35',
  pos: 'bg-pos-soft text-pos border-pos/30',
  neg: 'bg-neg-soft text-neg border-neg/30',
}

export function Badge({
  tone = 'neutral',
  children,
  className,
  title,
}: {
  tone?: Tone
  children: ReactNode
  className?: string
  title?: string
}) {
  return (
    <span
      title={title}
      className={clsx(
        'inline-flex h-5 items-center gap-1 rounded-md border px-1.5 text-[11px] font-medium whitespace-nowrap',
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

/** The in-sample warning used wherever results were selected on the same data they report. */
export function InSampleBadge({ className }: { className?: string }) {
  return (
    <Badge
      tone="warn"
      className={className}
      title="Parameters were selected on the same observations these results are measured on. Treat as an upper bound, not evidence."
    >
      In-sample
    </Badge>
  )
}

export function OutOfSampleBadge({ className }: { className?: string }) {
  return (
    <Badge
      tone="accent"
      className={className}
      title="Measured on observations not used to select parameters."
    >
      Out-of-sample
    </Badge>
  )
}
