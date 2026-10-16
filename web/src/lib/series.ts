// Helpers over the columnar TimeSeries shape returned by the API.

import type { Num, TimeSeries } from '@/api/types'
import { isNum } from './format'

export type Point = [string, number | null]

/** Zip dates with a column into ECharts [x, y] pairs; non-finite values become gaps. */
export function toPoints(dates: string[], values: readonly Num[] | undefined): Point[] {
  if (!values) return []
  return dates.map((date, index) => {
    const value = values[index]
    return [date, isNum(value) ? value : null]
  })
}

export function column(series: TimeSeries | null | undefined, name: string): Num[] | undefined {
  return series?.columns[name]
}

export function hasColumn(series: TimeSeries | null | undefined, name: string): boolean {
  const values = series?.columns[name]
  return !!values && values.some(isNum)
}

/** Columns with at least one finite value, in API order. */
export function nonEmptyColumns(series: TimeSeries | null | undefined): string[] {
  if (!series) return []
  return Object.keys(series.columns).filter((name) => series.columns[name].some(isNum))
}

export function firstFinite(values: readonly Num[] | undefined): number | null {
  if (!values) return null
  for (const value of values) if (isNum(value)) return value
  return null
}

export function lastFinite(values: readonly Num[] | undefined): number | null {
  if (!values) return null
  for (let i = values.length - 1; i >= 0; i--) {
    const value = values[i]
    if (isNum(value)) return value
  }
  return null
}

export function extent(values: readonly Num[] | undefined): [number, number] | null {
  let min = Infinity
  let max = -Infinity
  for (const value of values ?? []) {
    if (!isNum(value)) continue
    if (value < min) min = value
    if (value > max) max = value
  }
  return min <= max ? [min, max] : null
}

/** Rebase a series so its first finite value is 1. */
export function rebase(values: readonly Num[]): Num[] {
  const base = firstFinite(values)
  if (base === null || base === 0) return values.map(() => null)
  return values.map((value) => (isNum(value) ? value / base : null))
}

/**
 * Contiguous date ranges where `active(value)` holds, as [first date, last date] pairs.
 * Used to shade the periods a strategy holds a position.
 */
export function segments(
  dates: string[],
  values: readonly Num[] | undefined,
  active: (value: number) => boolean = (value) => value > 0,
): Array<[string, string]> {
  const result: Array<[string, string]> = []
  if (!values) return result
  let start: number | null = null
  for (let i = 0; i < dates.length; i++) {
    const value = values[i]
    const on = isNum(value) && active(value)
    if (on && start === null) start = i
    if (!on && start !== null) {
      result.push([dates[start], dates[i - 1]])
      start = null
    }
  }
  if (start !== null) result.push([dates[start], dates[dates.length - 1]])
  return result
}

/** Look up a column value by date (exact match), for placing trade markers. */
export function valueAtDate(
  dates: string[],
  values: readonly Num[] | undefined,
): (date: string) => number | null {
  const index = new Map(dates.map((date, i) => [date.slice(0, 10), i]))
  return (date) => {
    const i = index.get(date.slice(0, 10))
    if (i === undefined || !values) return null
    const value = values[i]
    return isNum(value) ? value : null
  }
}

/** Running drawdown of an equity curve as a negative fraction (0 at new highs). */
export function drawdown(values: readonly Num[]): Num[] {
  let peak = -Infinity
  return values.map((value) => {
    if (!isNum(value)) return null
    if (value > peak) peak = value
    return peak > 0 ? value / peak - 1 : null
  })
}
