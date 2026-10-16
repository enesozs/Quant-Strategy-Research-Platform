// The one implementation of the portfolio-assumption controls (ticker, dates, capital, costs,
// risk-free rate, cash yield, optional borrow fee) used by every research page.

import type { ReactNode } from 'react'
import { DateInput, NumberInput, Switch, TextInput } from '@/components/ui/Field'
import type { AssumptionValues } from '@/state/defaults'
import { FieldGroup } from './ControlPanel'

export function MarketFields<T extends AssumptionValues>({
  value,
  onChange,
  showTicker = true,
  startLabel = 'Start date',
  endLabel = 'End date',
  betweenDates,
}: {
  value: T
  onChange: (next: T) => void
  showTicker?: boolean
  startLabel?: string
  endLabel?: string
  /** Extra date field rendered under start and end (e.g. the out-of-sample split). */
  betweenDates?: ReactNode
}) {
  const patch = (fields: Partial<AssumptionValues>) => onChange({ ...value, ...fields })
  const datesInvalid = value.start_date >= value.end_date
  return (
    <>
      <FieldGroup title="Market">
        {showTicker && (
          <TextInput
            label="Ticker"
            value={value.ticker ?? ''}
            onChange={(ticker) => patch({ ticker })}
            uppercase
            mono
            placeholder="AAPL"
            error={value.ticker?.trim() ? undefined : 'Enter a ticker'}
          />
        )}
        <div className="grid grid-cols-2 items-end gap-3">
          <DateInput
            label={startLabel}
            value={value.start_date}
            onChange={(start_date) => patch({ start_date })}
          />
          <DateInput
            label={endLabel}
            value={value.end_date}
            onChange={(end_date) => patch({ end_date })}
            error={datesInvalid ? 'After start' : undefined}
          />
        </div>
        {betweenDates}
      </FieldGroup>

      <FieldGroup
        title="Costs & cash"
        collapsible
        defaultOpen={false}
        summary={assumptionSummary(value)}
      >
        <div className="grid grid-cols-2 items-end gap-3">
          <NumberInput
            label="Initial capital"
            value={value.initial_capital}
            onChange={(initial_capital) => patch({ initial_capital })}
            min={1}
            step={1000}
            suffix="$"
          />
          <NumberInput
            label="Cost (one-way)"
            value={value.transaction_cost_bps}
            onChange={(transaction_cost_bps) => patch({ transaction_cost_bps })}
            min={0}
            max={1000}
            step={1}
            suffix="bps"
          />
          <NumberInput
            label="Risk-free rate"
            value={value.risk_free_rate}
            onChange={(risk_free_rate) => patch({ risk_free_rate })}
            min={-0.5}
            max={0.5}
            step={0.0025}
            scale={100}
            suffix="%"
            hint="Annual; used for Sharpe"
          />
          {value.borrow_fee !== undefined && (
            <NumberInput
              label="Borrow fee"
              value={value.borrow_fee}
              onChange={(borrow_fee) => patch({ borrow_fee })}
              min={0}
              max={1}
              step={0.0025}
              scale={100}
              suffix="%"
              hint="Annual, short leg"
            />
          )}
        </div>
        <Switch
          label="Idle cash earns the risk-free rate"
          checked={value.cash_earns_risk_free}
          onChange={(cash_earns_risk_free) => patch({ cash_earns_risk_free })}
          hint={
            value.risk_free_rate === 0
              ? 'No effect while the risk-free rate is 0%.'
              : 'Uninvested capital accrues interest instead of 0%.'
          }
        />
      </FieldGroup>
    </>
  )
}

function assumptionSummary(value: AssumptionValues): string {
  const parts = [
    `$${value.initial_capital.toLocaleString('en-US')}`,
    `${value.transaction_cost_bps} bps`,
    `rf ${Number((value.risk_free_rate * 100).toPrecision(6))}%`,
  ]
  if (value.borrow_fee) parts.push(`borrow ${Number((value.borrow_fee * 100).toPrecision(6))}%`)
  return parts.join(' · ')
}
