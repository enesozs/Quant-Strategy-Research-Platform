// Pairs spread z-score with entry/exit/stop bands and trade markers.

import type { Num, Row } from '@/api/types'
import { formatDate, formatNumber, formatPercent, isNum } from '@/lib/format'
import { segments, toPoints, valueAtDate } from '@/lib/series'
import type { ChartColors } from '@/theme/chart'
import {
  axisTooltip,
  grid,
  legend,
  timeAxis,
  tooltipBox,
  tooltipHeader,
  tooltipRow,
  valueAxis,
  type ChartOption,
} from './base'

export interface Bands {
  entry: number
  exit: number
  stop: number
}

export function zscoreChart(
  c: ChartColors,
  data: {
    dates: string[]
    z: readonly Num[]
    position?: readonly Num[]
    trades: Row[]
    bands: Bands
  },
): ChartOption {
  const at = valueAtDate(data.dates, data.z)
  const entries: Array<{ value: [string, number]; trade: Row }> = []
  const exits: Array<{ value: [string, number]; trade: Row }> = []
  for (const trade of data.trades) {
    const entryDate = String(trade.entry_date ?? trade.signal_date ?? '')
    const exitDate = String(trade.exit_date ?? '')
    const ez = at(entryDate)
    const xz = at(exitDate)
    if (entryDate && ez !== null) entries.push({ value: [entryDate.slice(0, 10), ez], trade })
    if (exitDate && xz !== null) exits.push({ value: [exitDate.slice(0, 10), xz], trade })
  }

  const { entry, exit, stop } = data.bands
  const line = (value: number, color: string, label: string, type: 'dotted' | 'dashed') => ({
    yAxis: value,
    lineStyle: { color, type, width: 1 },
    label: { formatter: label, color: c.muted, fontSize: 10, position: 'insideEndTop' as const },
  })

  const tradeTooltip = (kind: 'Entry' | 'Exit') => (raw: unknown) => {
    const p = raw as { data: { value: [string, number]; trade: Row } }
    const t = p.data.trade
    let html = tooltipHeader(`${kind} · ${formatDate(p.data.value[0])}`)
    html += tooltipRow(c.ink2, formatNumber(p.data.value[1], 2), 'z-score')
    if (t.direction) html += tooltipRow(c.ink2, String(t.direction), 'direction')
    if (kind === 'Exit' && t.exit_reason)
      html += tooltipRow(c.ink2, String(t.exit_reason), 'exit reason')
    if (kind === 'Exit' && isNum(t.net_pair_return))
      html += tooltipRow(c.ink2, formatPercent(t.net_pair_return, 2), 'net return')
    return html
  }

  return {
    grid: grid(),
    legend: legend(c, { data: ['Spread z-score', 'Entries', 'Exits'] }),
    tooltip: axisTooltip(c, (v) => formatNumber(v, 2)),
    xAxis: timeAxis(c),
    yAxis: valueAxis(c, (v) => formatNumber(v, 0), { scale: false }),
    series: [
      {
        type: 'line',
        name: 'Spread z-score',
        data: toPoints(data.dates, data.z),
        showSymbol: false,
        sampling: 'lttb',
        color: c.series[0],
        lineStyle: { width: 1.5, color: c.series[0] },
        markArea: {
          silent: true,
          itemStyle: { color: c.band },
          data: segments(data.dates, data.position, (v) => v !== 0).map(([s, e]) => [
            { xAxis: s },
            { xAxis: e },
          ]),
        },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            line(stop, c.neg, `stop ±${formatNumber(stop, 1)}`, 'dashed'),
            line(-stop, c.neg, '', 'dashed'),
            line(entry, c.ink2, `entry ±${formatNumber(entry, 1)}`, 'dashed'),
            line(-entry, c.ink2, '', 'dashed'),
            line(exit, c.muted, `exit ±${formatNumber(exit, 1)}`, 'dotted'),
            line(-exit, c.muted, '', 'dotted'),
          ],
        },
      },
      {
        type: 'scatter',
        name: 'Entries',
        data: entries,
        symbol: 'triangle',
        symbolSize: 10,
        color: c.series[1],
        itemStyle: { borderColor: c.surface, borderWidth: 1.5 },
        tooltip: { trigger: 'item', ...tooltipBox(c), formatter: tradeTooltip('Entry') },
        z: 5,
      },
      {
        type: 'scatter',
        name: 'Exits',
        data: exits,
        symbol: 'circle',
        symbolSize: 8,
        color: c.series[2],
        itemStyle: { borderColor: c.surface, borderWidth: 1.5 },
        tooltip: { trigger: 'item', ...tooltipBox(c), formatter: tradeTooltip('Exit') },
        z: 5,
      },
    ],
  }
}
