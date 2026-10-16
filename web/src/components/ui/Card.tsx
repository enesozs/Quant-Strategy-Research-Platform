import clsx from 'clsx'
import type { ReactNode } from 'react'

export function Card({
  children,
  className,
  as: Tag = 'section',
  ...rest
}: {
  children: ReactNode
  className?: string
  as?: 'section' | 'div' | 'article' | 'aside'
  'aria-labelledby'?: string
}) {
  return (
    <Tag
      className={clsx('min-w-0 rounded-xl border border-line bg-surface shadow-card', className)}
      {...rest}
    >
      {children}
    </Tag>
  )
}

/** A titled result block: heading, optional description and actions, then content. */
export function Panel({
  title,
  description,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <Card className={className}>
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-4 pt-4 sm:px-5">
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h2>
          {description && (
            <p className="mt-0.5 text-[13px] leading-snug text-muted">{description}</p>
          )}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </header>
      <div className={clsx('px-4 pt-3 pb-4 sm:px-5', bodyClassName)}>{children}</div>
    </Card>
  )
}
