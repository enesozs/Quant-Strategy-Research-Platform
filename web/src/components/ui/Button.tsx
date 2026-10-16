import clsx from 'clsx'
import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-accent text-accent-ink hover:brightness-110 active:brightness-95 disabled:bg-surface-3 disabled:text-muted',
  secondary:
    'bg-surface text-ink border border-line-strong hover:bg-surface-2 disabled:text-muted disabled:hover:bg-surface',
  ghost: 'text-ink-2 hover:bg-surface-2 hover:text-ink disabled:text-muted',
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  type = 'button',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' }) {
  return (
    <button
      type={type}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap transition-[background-color,filter,color] disabled:cursor-not-allowed',
        size === 'md' ? 'h-9 px-3.5 text-sm' : 'h-7 px-2.5 text-xs',
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  )
}
