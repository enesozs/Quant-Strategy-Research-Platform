// Every number and date shown in the app goes through this file.
// Inputs follow the API contract: rates/returns are decimal fractions, nulls mean "undefined".

export const DASH = '—'
const MINUS = '−'

export function isNum(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/** Replace the ASCII hyphen of a negative number with a typographic minus. */
function minus(text: string): string {
  return text.startsWith('-') ? MINUS + text.slice(1) : text
}

/** Avoid printing "-0.0%" for values that round to zero. */
function clean(value: number, digits: number): number {
  const rounded = Number(value.toFixed(digits))
  return Object.is(rounded, -0) || rounded === 0 ? 0 : value
}

function fixed(value: number, digits: number): string {
  return clean(value, digits).toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function formatNumber(value: unknown, digits = 2): string {
  return isNum(value) ? minus(fixed(value, digits)) : DASH
}

export function formatSignedNumber(value: unknown, digits = 2): string {
  if (!isNum(value)) return DASH
  const text = fixed(value, digits)
  return clean(value, digits) > 0 ? `+${text}` : minus(text)
}

export function formatInteger(value: unknown): string {
  return isNum(value) ? minus(Math.round(value).toLocaleString('en-US')) : DASH
}

/** 0.1234 → "12.3%". */
export function formatPercent(value: unknown, digits = 1): string {
  return isNum(value) ? `${minus(fixed(value * 100, digits))}%` : DASH
}

/** 0.1234 → "+12.3%"; used for deltas. */
export function formatSignedPercent(value: unknown, digits = 1): string {
  if (!isNum(value)) return DASH
  return `${formatSignedNumber(value * 100, digits)}%`
}

/** Percentage-point delta between two fractions, e.g. "+3.1 pp". */
export function formatPointDelta(value: unknown, digits = 1): string {
  return isNum(value) ? `${formatSignedNumber(value * 100, digits)} pp` : DASH
}

/** Sharpe, Calmar and other ratios: two decimals. */
export function formatRatio(value: unknown, digits = 2): string {
  return formatNumber(value, digits)
}

export function formatCurrency(value: unknown, { compact = false } = {}): string {
  if (!isNum(value)) return DASH
  const text = Math.abs(value).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: compact ? 1 : 0,
    minimumFractionDigits: 0,
  })
  return value < 0 && clean(value, 0) !== 0 ? `${MINUS}${text}` : text
}

/** Cumulative one-way turnover in multiples of capital: 12.34 → "12.3×". */
export function formatMultiple(value: unknown, digits = 1): string {
  return isNum(value) ? `${minus(fixed(value, digits))}×` : DASH
}

export function formatPValue(value: unknown): string {
  if (!isNum(value)) return DASH
  if (value < 0.001) return '<0.001'
  return fixed(value, 3)
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function parseIsoDate(value: string): [number, number, number] | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  return match ? [Number(match[1]), Number(match[2]), Number(match[3])] : null
}

/** "2020-01-03" → "Jan 3, 2020". Parsed by hand so the user's timezone never shifts the day. */
export function formatDate(value: unknown): string {
  if (typeof value !== 'string') return DASH
  const parts = parseIsoDate(value)
  if (!parts) return value
  const [year, month, day] = parts
  return `${MONTHS[month - 1]} ${day}, ${year}`
}

/** "2020-01-03" → "Jan 2020". */
export function formatMonth(value: unknown): string {
  if (typeof value !== 'string') return DASH
  const parts = parseIsoDate(value)
  return parts ? `${MONTHS[parts[1] - 1]} ${parts[0]}` : value
}

export function formatDateRange(start: unknown, end: unknown): string {
  return `${formatDate(start)} – ${formatDate(end)}`
}

/** Elapsed time for long-running requests: 4200 → "4s", 65000 → "1m 05s". */
export function formatElapsed(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`
}

// ---------------------------------------------------------------------------------------------
// Value kinds: one formatter per kind, shared by tables, tiles and tooltips.

export type ValueKind =
  | 'percent'
  | 'signedPercent'
  | 'ratio'
  | 'signedRatio'
  | 'number'
  | 'integer'
  | 'currency'
  | 'multiple'
  | 'pvalue'
  | 'date'
  | 'boolean'
  | 'text'

export function formatValue(kind: ValueKind, value: unknown): string {
  if (value === null || value === undefined || value === '') return DASH
  switch (kind) {
    case 'percent':
      return formatPercent(value)
    case 'signedPercent':
      return formatSignedPercent(value)
    case 'ratio':
      return formatRatio(value)
    case 'signedRatio':
      return formatSignedNumber(value)
    case 'number':
      return isNum(value) ? formatGeneral(value) : String(value)
    case 'integer':
      return formatInteger(value)
    case 'currency':
      return formatCurrency(value)
    case 'multiple':
      return formatMultiple(value)
    case 'pvalue':
      return formatPValue(value)
    case 'date':
      return formatDate(value)
    case 'boolean':
      return value === true ? 'Yes' : value === false ? 'No' : String(value)
    case 'text':
      return typeof value === 'number'
        ? formatNumber(value, Number.isInteger(value) ? 0 : 3)
        : String(value)
  }
}

/** Generic number: integers plain, large values 1dp, tiny values by significant digits. */
export function formatGeneral(value: number): string {
  if (Number.isInteger(value)) return formatInteger(value)
  const abs = Math.abs(value)
  if (abs >= 10) return formatNumber(value, 1)
  if (abs > 0 && abs < 0.001) return minus(String(Number(value.toPrecision(3))))
  return formatNumber(value, 3)
}

/** True for kinds that should be right-aligned in tables. */
export function isNumericKind(kind: ValueKind): boolean {
  return kind !== 'text' && kind !== 'boolean' && kind !== 'date'
}

// ---------------------------------------------------------------------------------------------
// Metrics and objectives

export const METRIC_LABELS: Record<string, string> = {
  total_return: 'Total return',
  cagr: 'CAGR',
  annualized_volatility: 'Volatility',
  sharpe_ratio: 'Sharpe',
  max_drawdown: 'Max drawdown',
  calmar_ratio: 'Calmar',
  final_value: 'Final value',
  rebalancing_days: 'Rebalancing days',
  turnover: 'Turnover',
  average_exposure: 'Avg exposure',
}

export const METRIC_KINDS: Record<string, ValueKind> = {
  total_return: 'percent',
  cagr: 'percent',
  annualized_volatility: 'percent',
  sharpe_ratio: 'ratio',
  max_drawdown: 'percent',
  calmar_ratio: 'ratio',
  final_value: 'currency',
  rebalancing_days: 'integer',
  turnover: 'multiple',
  average_exposure: 'percent',
}

/** Whether a larger value of the metric is better (drawdown is negative, so larger is better). */
export const METRIC_HIGHER_IS_BETTER: Record<string, boolean> = {
  total_return: true,
  cagr: true,
  annualized_volatility: false,
  sharpe_ratio: true,
  max_drawdown: true,
  calmar_ratio: true,
  final_value: true,
}

export function formatMetric(key: string, value: unknown): string {
  return formatValue(METRIC_KINDS[key] ?? 'number', value)
}

/** Delta of a metric vs a reference, in the metric's own units ("+3.1 pp" or "+0.24"). */
export function formatMetricDelta(key: string, delta: unknown): string {
  const kind = METRIC_KINDS[key] ?? 'number'
  if (kind === 'percent') return formatPointDelta(delta)
  if (kind === 'currency')
    return isNum(delta) ? (delta >= 0 ? '+' : '') + formatCurrency(delta) : DASH
  return formatSignedNumber(delta)
}

export function formatObjective(format: 'percent' | 'ratio', value: unknown): string {
  return format === 'percent' ? formatPercent(value, 2) : formatRatio(value)
}

// ---------------------------------------------------------------------------------------------
// Parameters and labels

export interface ParamFormat {
  type?: 'int' | 'float'
  format?: 'percent'
}

export function formatParameterValue(value: unknown, spec?: ParamFormat): string {
  if (!isNum(value)) return value === null || value === undefined ? DASH : String(value)
  if (spec?.format === 'percent') return formatPercent(value, value * 100 < 10 ? 1 : 0)
  if (spec?.type === 'int' || Number.isInteger(value)) return formatInteger(value)
  return minus(String(Number(value.toPrecision(6))))
}

/** "fast_window" → "Fast window"; known abbreviations keep their case. */
export function humanize(key: string): string {
  const text = key.replace(/::/g, ' ').replace(/_/g, ' ').trim()
  const words = text.split(/\s+/).map((word) => {
    const upper = word.toUpperCase()
    if (
      [
        'CAGR',
        'OOS',
        'ADF',
        'ATR',
        'RSI',
        'CCI',
        'ADX',
        'MACD',
        'EMA',
        'DI',
        'OLS',
        'MA',
        'K',
        'D',
      ].includes(upper)
    )
      return upper
    return word.toLowerCase()
  })
  const sentence = words.join(' ')
  return sentence.charAt(0).toUpperCase() + sentence.slice(1)
}

export type DeltaTone = 'pos' | 'neg' | 'neutral'

/** Tone for a delta given whether higher is better; tiny deltas stay neutral. */
export function deltaTone(key: string, delta: number | null): DeltaTone {
  if (delta === null || Math.abs(delta) < 1e-9) return 'neutral'
  const higher = METRIC_HIGHER_IS_BETTER[key]
  if (higher === undefined) return 'neutral'
  return delta > 0 === higher ? 'pos' : 'neg'
}

/** Axis tick for fractions: whole percentages when the tick is whole, else one decimal. */
export function formatPercentTick(value: number): string {
  const pct = Math.round(value * 1000) / 10
  return formatPercent(value, Number.isInteger(pct) ? 0 : 1)
}
