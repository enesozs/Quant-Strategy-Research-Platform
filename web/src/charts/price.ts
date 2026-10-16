// Price with indicator overlays and position shading; oscillators on their own panel below
// (a separate grid with its own scale, never a second axis on the price panel).

import type { Num, TimeSeries } from '@/api/types'
import { formatNumber, humanize } from '@/lib/format'
import { nonEmptyColumns, segments, toPoints } from '@/lib/series'
import type { ChartColors } from '@/theme/chart'
import { axisChrome, axisTooltip, legend, timeAxis, valueAxis, type ChartOption } from './base'

export function priceChart(
  c: ChartColors,
  data: {
    dates: string[]
    close: readonly Num[]
    position: readonly Num[] | undefined
    overlays: TimeSeries
    oscillators: TimeSeries | null
    /** Horizontal reference levels on the oscillator panel (e.g. RSI entry/exit thresholds). */
    thresholds?: Array<{ value: number; label: string }>
  },
): ChartOption {
  const overlayNames = nonEmptyColumns(data.overlays)
  const oscillatorNames = data.oscillators ? nonEmptyColumns(data.oscillators) : []
  const hasOsc = oscillatorNames.length > 0
  const priceFormat = (value: number) => formatNumber(value, Math.abs(value) >= 10 ? 0 : 2)
  const overlayValues = (name: string) =>
    alignTo(data.dates, data.overlays.dates, data.overlays.columns[name])

  const series: NonNullable<ChartOption['series']> = [
    {
      type: 'line',
      name: 'Close',
      data: toPoints(data.dates, data.close),
      showSymbol: false,
      sampling: 'lttb',
      color: c.ink2,
      lineStyle: { width: 1.25, color: c.ink2 },
      z: 3,
      markArea: {
        silent: true,
        itemStyle: { color: c.band },
        data: segments(data.dates, data.position).map(([start, end]) => [
          { xAxis: start },
          { xAxis: end },
        ]),
      },
    },
    ...overlayNames.map((name, index) => ({
      type: 'line' as const,
      name: humanize(name),
      data: toPoints(data.dates, overlayValues(name)),
      showSymbol: false,
      sampling: 'lttb' as const,
      color: c.series[index % c.series.length],
      lineStyle: { width: 1.5, color: c.series[index % c.series.length] },
      z: 2,
    })),
  ]

  if (hasOsc && data.oscillators) {
    const osc = data.oscillators
    oscillatorNames.forEach((name, index) => {
      const color = c.series[(overlayNames.length + index) % c.series.length]
      const isHistogram = name.includes('hist')
      const levels = index === 0 ? (data.thresholds ?? []) : []
      series.push({
        markLine: levels.length
          ? {
              silent: true,
              symbol: 'none',
              data: levels.map((level) => ({
                yAxis: level.value,
                lineStyle: { color: c.muted, type: 'dashed', width: 1 },
                label: {
                  formatter: level.label,
                  color: c.muted,
                  fontSize: 10,
                  position: 'insideEndTop',
                },
              })),
            }
          : undefined,
        type: isHistogram ? ('bar' as const) : ('line' as const),
        name: humanize(name),
        data: toPoints(data.dates, alignTo(data.dates, osc.dates, osc.columns[name])),
        xAxisIndex: 1,
        yAxisIndex: 1,
        showSymbol: false,
        color,
        ...(isHistogram
          ? { itemStyle: { color, opacity: 0.45 }, barMaxWidth: 3 }
          : { lineStyle: { width: 1.5, color }, sampling: 'lttb' as const }),
      } as never)
    })
  }

  const legendNames = series.map((s) => (s as { name: string }).name)
  return {
    legend: legend(c, { data: legendNames }),
    tooltip: axisTooltip(c, (value) => formatNumber(value, 2)),
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: hasOsc
      ? [
          { left: 4, right: 12, top: 34, height: '58%', containLabel: true },
          { left: 4, right: 12, top: '74%', bottom: 4, containLabel: true },
        ]
      : [{ left: 4, right: 12, top: 34, bottom: 4, containLabel: true }],
    xAxis: hasOsc
      ? [timeAxis(c, { gridIndex: 0, axisLabel: { show: false } }), timeAxis(c, { gridIndex: 1 })]
      : [timeAxis(c)],
    yAxis: hasOsc
      ? [
          valueAxis(c, priceFormat, { gridIndex: 0 }),
          valueAxis(c, (v) => formatNumber(v, Math.abs(v) < 10 ? 1 : 0), {
            gridIndex: 1,
            splitNumber: 2,
            ...axisChromeLabels(c),
          }),
        ]
      : [valueAxis(c, priceFormat)],
    series,
  }
}

function axisChromeLabels(c: ChartColors) {
  return { axisLabel: { ...axisChrome(c).axisLabel, fontSize: 10 } }
}

/** Indicator frames normally share the price dates; align defensively when they don't. */
function alignTo(target: string[], source: string[], values: readonly Num[] | undefined): Num[] {
  if (!values) return target.map(() => null)
  if (source.length === target.length && source[0] === target[0]) return [...values]
  const index = new Map(source.map((date, i) => [date, i]))
  return target.map((date) => {
    const i = index.get(date)
    return i === undefined ? null : values[i]
  })
}
