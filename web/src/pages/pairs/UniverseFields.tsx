import type { Meta } from '@/api/types'
import { FieldGroup } from '@/components/controls/ControlPanel'
import { NumberInput, Select, TextArea } from '@/components/ui/Field'
import type { Setter } from '@/state/store'
import { parseTickers, type UniverseForm } from './state'

const CUSTOM = '__custom__'

export function UniverseFields({
  meta,
  universe,
  setUniverse,
  topNKey,
}: {
  meta: Meta
  universe: UniverseForm
  setUniverse: Setter<UniverseForm>
  topNKey: 'discover_top_n' | 'portfolio_top_n'
}) {
  const presets = meta.universe_presets
  const tickers = parseTickers(universe.tickers)
  const pairs = (tickers.length * (tickers.length - 1)) / 2
  return (
    <FieldGroup title="Universe">
      <Select
        label="Preset"
        value={presets[universe.preset] ? universe.preset : CUSTOM}
        onChange={(preset) =>
          setUniverse((u) =>
            preset === CUSTOM
              ? { ...u, preset: CUSTOM }
              : { ...u, preset, tickers: (presets[preset] ?? []).join(', ') },
          )
        }
        options={[
          ...Object.keys(presets).map((name) => ({ value: name, label: name })),
          { value: CUSTOM, label: 'Custom' },
        ]}
      />
      <TextArea
        label="Candidate tickers"
        value={universe.tickers}
        onChange={(text) =>
          setUniverse((u) => ({
            ...u,
            tickers: text,
            preset: presets[u.preset]?.join(', ') === text ? u.preset : CUSTOM,
          }))
        }
        mono
        hint={`${tickers.length} tickers · ${pairs} candidate pairs. Every ticker is downloaded; ones that fail are skipped.`}
      />
      <div className="grid grid-cols-2 items-end gap-3">
        <NumberInput
          label="Selection window (years)"
          value={universe.formation_years}
          onChange={(formation_years) => setUniverse((u) => ({ ...u, formation_years }))}
          min={1}
          max={10}
          step={1}
          integer
        />
        <NumberInput
          label={topNKey === 'discover_top_n' ? 'Pairs to show' : 'Pairs to trade'}
          value={universe[topNKey]}
          onChange={(n) => setUniverse((u) => ({ ...u, [topNKey]: n }))}
          min={1}
          max={topNKey === 'discover_top_n' ? 50 : 20}
          step={1}
          integer
        />
      </div>
    </FieldGroup>
  )
}
