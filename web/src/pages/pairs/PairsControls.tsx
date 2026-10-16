// Method picker and method-specific parameter groups, shared by the three pairs pages.

import type { Meta, PairsMethod } from '@/api/types'
import { FieldGroup } from '@/components/controls/ControlPanel'
import { Button } from '@/components/ui/Button'
import { NumberInput, Segmented, Switch } from '@/components/ui/Field'
import { methodGroups, resolveParams } from './params'
import type { PairsForm } from './state'
import type { Setter } from '@/state/store'

export function MethodField({
  meta,
  form,
  setForm,
}: {
  meta: Meta
  form: PairsForm
  setForm: Setter<PairsForm>
}) {
  const methods = meta.pairs_methods.length
    ? meta.pairs_methods
    : [
        { key: 'distance', label: 'Distance', description: '' },
        { key: 'cointegration', label: 'Cointegration', description: '' },
        { key: 'kalman', label: 'Kalman', description: '' },
      ]
  const current = methods.find((m) => m.key === form.method)
  return (
    <div className="space-y-1.5">
      <Segmented
        label="Spread model"
        value={form.method}
        onChange={(method) => setForm((f) => ({ ...f, method: method as PairsMethod }))}
        options={methods.map((m) => ({ value: m.key as PairsMethod, label: shortLabel(m.label) }))}
        size="sm"
      />
      {current?.description && (
        <p className="text-xs leading-snug text-muted">{current.description}</p>
      )}
    </div>
  )
}

function shortLabel(label: string): string {
  return label.replace(/ hedge ratio$/i, '')
}

export function MethodParamFields({
  form,
  setForm,
  hide = [],
  collapsed = false,
}: {
  form: PairsForm
  setForm: Setter<PairsForm>
  hide?: string[]
  collapsed?: boolean
}) {
  const params = resolveParams(form.method, form.params[form.method])
  const set = (key: string, value: number | boolean) =>
    setForm((f) => ({
      ...f,
      params: {
        ...f.params,
        [f.method]: { ...resolveParams(f.method, f.params[f.method]), [key]: value },
      },
    }))
  const reset = () => setForm((f) => ({ ...f, params: { ...f.params, [f.method]: undefined } }))
  return (
    <>
      {methodGroups(form.method).map((group, gi) => {
        const visible = group.params.filter((p) => !hide.includes(p.key))
        if (!visible.length) return null
        return (
          <FieldGroup
            key={`${form.method}:${group.title}`}
            title={group.title}
            collapsible
            defaultOpen={!collapsed && (group.title === 'Trading rules' || gi === 0)}
            summary={visible
              .filter((p) => p.kind !== 'bool')
              .slice(0, 3)
              .map((p) => `${p.label.split(' (')[0]} ${String(params[p.key])}`)
              .join(' · ')}
          >
            <div className="grid grid-cols-2 items-end gap-3">
              {visible.map((p) =>
                p.kind === 'bool' ? (
                  <Switch
                    key={p.key}
                    className="col-span-2"
                    label={p.label}
                    hint={p.hint}
                    checked={Boolean(params[p.key])}
                    onChange={(v) => set(p.key, v)}
                  />
                ) : (
                  <NumberInput
                    key={p.key}
                    label={p.label}
                    hint={p.hint}
                    className={p.hint ? 'col-span-2' : undefined}
                    value={Number(params[p.key])}
                    onChange={(v) => set(p.key, v)}
                    min={p.min}
                    max={p.max}
                    step={p.step}
                    integer={p.kind === 'int'}
                  />
                ),
              )}
            </div>
            {group.title === 'Trading rules' && (
              <Button size="sm" variant="ghost" onClick={reset}>
                Reset {form.method} parameters
              </Button>
            )}
          </FieldGroup>
        )
      })}
    </>
  )
}
