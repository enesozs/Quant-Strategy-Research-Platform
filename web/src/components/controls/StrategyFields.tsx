import type { ReactNode } from 'react'
import { useMeta } from '@/api/client'
import type { Meta, Objective, Parameters, StrategyMeta } from '@/api/types'
import { Alert } from '@/components/ui/Alert'
import { NumberInput, Select } from '@/components/ui/Field'
import { Skeleton } from '@/components/ui/Skeleton'
import { findStrategy, findObjective } from '@/lib/meta'

/** Renders children with loaded metadata; otherwise a skeleton or an error. */
export function WithMeta({ children }: { children: (meta: Meta) => ReactNode }) {
  const meta = useMeta()
  if (meta.data) return <>{children(meta.data)}</>
  if (meta.isError)
    return (
      <Alert
        tone="error"
        title="Could not load strategy metadata"
        action={
          <button
            className="text-xs font-medium text-accent hover:underline"
            onClick={() => meta.refetch()}
          >
            Retry
          </button>
        }
      >
        {meta.error.message}
      </Alert>
    )
  return (
    // Settings live in the sidebar on desktop, so only the results area needs a placeholder.
    <div className="grid gap-5">
      <Skeleton className="h-96 rounded-xl lg:hidden" />
      <Skeleton className="h-96 rounded-xl" />
    </div>
  )
}

export function StrategySelect({
  meta,
  value,
  onChange,
}: {
  meta: Meta
  value: string
  onChange: (key: string) => void
}) {
  return (
    <Select
      label="Strategy"
      value={value}
      onChange={onChange}
      options={meta.strategies.map((s) => ({
        value: s.key,
        label: s.display_name,
        group: s.family,
      }))}
      hint={findStrategy(meta, value)?.description}
    />
  )
}

export function ObjectiveSelect({
  meta,
  value,
  onChange,
  label = 'Objective',
}: {
  meta: Meta
  value: Objective
  onChange: (key: Objective) => void
  label?: string
}) {
  const objective = findObjective(meta, value)
  return (
    <Select
      label={label}
      value={value}
      onChange={onChange}
      options={meta.objectives.map((o) => ({ value: o.key, label: o.label }))}
      hint={objective.higher_is_better ? 'Higher is better' : 'Lower is better'}
    />
  )
}

export function ParameterFields({
  strategy,
  values,
  onChange,
}: {
  strategy: StrategyMeta
  values: Parameters
  onChange: (values: Parameters) => void
}) {
  const entries = Object.entries(strategy.parameters)
  return (
    <div className="grid grid-cols-2 items-end gap-3">
      {entries.map(([key, spec]) => {
        const percent = spec.format === 'percent'
        return (
          <NumberInput
            key={`${strategy.key}:${key}`}
            label={spec.label}
            value={values[key] ?? spec.default}
            onChange={(v) => onChange({ ...values, [key]: v })}
            min={spec.min}
            max={spec.max}
            step={spec.step}
            integer={spec.type === 'int'}
            scale={percent ? 100 : 1}
            suffix={percent ? '%' : undefined}
            className={entries.length === 1 ? 'col-span-2' : undefined}
          />
        )
      })}
    </div>
  )
}
