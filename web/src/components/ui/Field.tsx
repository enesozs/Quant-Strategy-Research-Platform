// Form controls. Every input has a visible <label>; numbers keep a local text draft so partial
// entries ("0.", "-") don't fight the parsed value.

import clsx from 'clsx'
import { useId, useState, type ReactNode } from 'react'
import { Icon } from './Icon'

const INPUT =
  'h-9 w-full min-w-0 rounded-lg border border-line-strong bg-surface px-2.5 text-sm text-ink placeholder:text-muted transition-colors hover:border-muted/60 focus:border-accent focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-ring disabled:opacity-60'

export function Field({
  label,
  hint,
  error,
  children,
  htmlFor,
  className,
}: {
  label: ReactNode
  hint?: ReactNode
  error?: ReactNode
  children: ReactNode
  htmlFor: string
  className?: string
}) {
  return (
    <div className={clsx('min-w-0', className)}>
      <label htmlFor={htmlFor} className="mb-1 block text-xs font-medium text-ink-2">
        {label}
      </label>
      {children}
      {error ? (
        <p className="mt-1 text-xs text-neg">{error}</p>
      ) : hint ? (
        <p className="mt-1 text-xs leading-snug text-muted">{hint}</p>
      ) : null}
    </div>
  )
}

export function TextInput({
  label,
  value,
  onChange,
  hint,
  error,
  placeholder,
  mono,
  uppercase,
  className,
}: {
  label: ReactNode
  value: string
  onChange: (value: string) => void
  hint?: ReactNode
  error?: ReactNode
  placeholder?: string
  mono?: boolean
  uppercase?: boolean
  className?: string
}) {
  const id = useId()
  return (
    <Field label={label} hint={hint} error={error} htmlFor={id} className={className}>
      <input
        id={id}
        type="text"
        value={value}
        placeholder={placeholder}
        spellCheck={false}
        autoComplete="off"
        aria-invalid={!!error || undefined}
        onChange={(event) =>
          onChange(uppercase ? event.target.value.toUpperCase() : event.target.value)
        }
        className={clsx(INPUT, mono && 'font-mono text-[13px] tracking-wide')}
      />
    </Field>
  )
}

export function TextArea({
  label,
  value,
  onChange,
  hint,
  rows = 3,
  mono,
  className,
}: {
  label: ReactNode
  value: string
  onChange: (value: string) => void
  hint?: ReactNode
  rows?: number
  mono?: boolean
  className?: string
}) {
  const id = useId()
  return (
    <Field label={label} hint={hint} htmlFor={id} className={className}>
      <textarea
        id={id}
        value={value}
        rows={rows}
        spellCheck={false}
        onChange={(event) => onChange(event.target.value)}
        className={clsx(INPUT, 'h-auto py-2 leading-relaxed', mono && 'font-mono text-[13px]')}
      />
    </Field>
  )
}

export function DateInput({
  label,
  value,
  onChange,
  hint,
  error,
  className,
}: {
  label: ReactNode
  value: string
  onChange: (value: string) => void
  hint?: ReactNode
  error?: ReactNode
  className?: string
}) {
  const id = useId()
  return (
    <Field label={label} hint={hint} error={error} htmlFor={id} className={className}>
      <input
        id={id}
        type="date"
        value={value}
        aria-invalid={!!error || undefined}
        onChange={(event) => event.target.value && onChange(event.target.value)}
        className={clsx(INPUT, 'num font-mono text-[13px]')}
      />
    </Field>
  )
}

/**
 * Numeric input. `scale` converts between stored and displayed units (100 shows a decimal
 * fraction as a percentage). Invalid drafts are not committed.
 */
export function NumberInput({
  label,
  value,
  onChange,
  min,
  max,
  step,
  scale = 1,
  suffix,
  integer,
  hint,
  error,
  className,
}: {
  label: ReactNode
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  scale?: number
  suffix?: string
  integer?: boolean
  hint?: ReactNode
  error?: ReactNode
  className?: string
}) {
  const id = useId()
  const display = (v: number) => String(Number((v * scale).toPrecision(10)))
  // While focused the user's text is authoritative; otherwise the field shows the stored value,
  // so external changes (e.g. "apply recommended") appear without syncing state in an effect.
  const [editing, setEditing] = useState<string | null>(null)
  const draft = editing ?? display(value)
  const isValid = (text: string) => {
    const n = Number(text)
    return (
      text.trim() !== '' &&
      Number.isFinite(n) &&
      (!integer || Number.isInteger(n)) &&
      (min === undefined || n / scale >= min - 1e-12) &&
      (max === undefined || n / scale <= max + 1e-12)
    )
  }
  const draftValid = isValid(draft)
  const rangeHint =
    min !== undefined && max !== undefined
      ? `Between ${display(min)} and ${display(max)}${integer ? ', whole number' : ''}`
      : min !== undefined
        ? `At least ${display(min)}`
        : 'Enter a number'

  return (
    <Field
      label={label}
      hint={hint}
      error={error ?? (!draftValid ? rangeHint : undefined)}
      htmlFor={id}
      className={className}
    >
      <div className="relative">
        <input
          id={id}
          type="text"
          inputMode="decimal"
          value={draft}
          aria-invalid={!draftValid || undefined}
          onFocus={() => setEditing(display(value))}
          onBlur={() => setEditing(null)}
          onChange={(event) => {
            const text = event.target.value
            setEditing(text)
            if (isValid(text)) {
              const next = Number(text)
              onChange(scale === 1 ? next : Number((next / scale).toPrecision(12)))
            }
          }}
          onKeyDown={(event) => {
            if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
            event.preventDefault()
            const delta = (step ?? 1) * (event.key === 'ArrowUp' ? 1 : -1)
            let next = Number((value + delta).toPrecision(12))
            if (min !== undefined) next = Math.max(min, next)
            if (max !== undefined) next = Math.min(max, next)
            onChange(next)
            setEditing(display(next))
          }}
          className={clsx(
            INPUT,
            'num font-mono text-[13px]',
            suffix && 'pr-9',
            !draftValid && 'border-neg',
          )}
        />
        {suffix && (
          <span className="pointer-events-none absolute inset-y-0 right-2.5 flex items-center text-xs text-muted">
            {suffix}
          </span>
        )}
      </div>
    </Field>
  )
}

export function Select<T extends string>({
  label,
  value,
  onChange,
  options,
  hint,
  className,
}: {
  label: ReactNode
  value: T
  onChange: (value: T) => void
  options: Array<{ value: T; label: string; group?: string }>
  hint?: ReactNode
  className?: string
}) {
  const id = useId()
  const groups = [...new Set(options.map((o) => o.group ?? ''))]
  const renderOptions = (items: typeof options) =>
    items.map((option) => (
      <option key={option.value} value={option.value}>
        {option.label}
      </option>
    ))
  return (
    <Field label={label} hint={hint} htmlFor={id} className={className}>
      <div className="relative">
        <select
          id={id}
          value={value}
          onChange={(event) => onChange(event.target.value as T)}
          className={clsx(INPUT, 'appearance-none pr-8')}
        >
          {groups.length > 1
            ? groups.map((group) => (
                <optgroup key={group} label={group}>
                  {renderOptions(options.filter((o) => (o.group ?? '') === group))}
                </optgroup>
              ))
            : renderOptions(options)}
        </select>
        <Icon
          name="chevronDown"
          className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-muted"
        />
      </div>
    </Field>
  )
}

export function Switch({
  label,
  checked,
  onChange,
  hint,
  className,
}: {
  label: ReactNode
  checked: boolean
  onChange: (checked: boolean) => void
  hint?: ReactNode
  className?: string
}) {
  const id = useId()
  return (
    <div className={clsx('flex items-start justify-between gap-3', className)}>
      <div className="min-w-0">
        <label htmlFor={id} className="block cursor-pointer text-[13px] font-medium text-ink">
          {label}
        </label>
        {hint && <p className="mt-0.5 text-xs leading-snug text-muted">{hint}</p>}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={clsx(
          'relative mt-0.5 inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors',
          checked ? 'bg-accent' : 'bg-surface-3 ring-1 ring-line-strong ring-inset',
        )}
      >
        <span
          className={clsx(
            'inline-block size-4 rounded-full bg-white shadow transition-transform',
            checked ? 'translate-x-[18px]' : 'translate-x-0.5',
          )}
        />
      </button>
    </div>
  )
}

/** Segmented control (a radio group styled as connected buttons). */
export function Segmented<T extends string>({
  label,
  value,
  onChange,
  options,
  className,
  size = 'md',
}: {
  label: string
  value: T
  onChange: (value: T) => void
  options: Array<{ value: T; label: string }>
  className?: string
  size?: 'sm' | 'md'
}) {
  const id = useId()
  return (
    <div className={clsx('min-w-0', className)}>
      <span className="mb-1 block text-xs font-medium text-ink-2" id={id}>
        {label}
      </span>
      <div
        role="radiogroup"
        aria-labelledby={id}
        className="flex w-full rounded-lg border border-line-strong bg-surface-2 p-0.5"
      >
        {options.map((option) => {
          const active = option.value === value
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(option.value)}
              className={clsx(
                'min-w-0 flex-1 truncate rounded-md font-medium transition-colors',
                size === 'md' ? 'h-8 px-2 text-[13px]' : 'h-7 px-1 text-xs',
                active
                  ? 'bg-surface text-ink shadow-card ring-1 ring-line'
                  : 'text-muted hover:text-ink',
              )}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
