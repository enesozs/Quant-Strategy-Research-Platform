// Cross-strategy charts: risk vs return scatter and max drawdown bars.

import { formatPercent, formatPercentTick, formatRatio } from '@/lib/format'
import type { ChartColors } from '@/theme/chart'
import {
  axisChrome,
  grid,
  tooltipBox,
  tooltipHeader,
  tooltipRow,
  valueAxis,
  type ChartOption,
} from './base'

export interface StrategyPoint {
  key: string
  name: string
  volatility: number
  cagr: number
  sharpe: number | null
  maxDrawdown: number
  benchmark: boolean
}

export function riskReturnChart(c: ChartColors, points: StrategyPoint[]): ChartOption {
  // The cluster is too dense for direct labels: names appear on hover (and in the tooltip and the
  // rankings table); only the Buy and Hold reference is labelled.
  const item = (p: StrategyPoint) => ({
    value: [p.volatility, p.cagr],
    name: p.name,
    point: p,
    label: { show: p.benchmark },
  })
  const tooltip = (raw: unknown) => {
    const p = (raw as { data: { point: StrategyPoint } }).data.point
    return (
      tooltipHeader(p.name) +
      tooltipRow(c.ink2, formatPercent(p.cagr), 'CAGR') +
      tooltipRow(c.ink2, formatPercent(p.volatility), 'volatility') +
      tooltipRow(c.ink2, formatRatio(p.sharpe), 'Sharpe')
    )
  }
  const label = {
    show: true,
    formatter: (raw: unknown) => (raw as { name: string }).name,
    position: 'top' as const,
    distance: 8,
    color: c.ink2,
    fontSize: 11,
  }
  return {
    grid: grid({ top: 30, bottom: 26, left: 8, right: 36 }),
    tooltip: { trigger: 'item', ...tooltipBox(c), formatter: tooltip },
    xAxis: {
      ...valueAxis(c, (v) => formatPercentTick(v)),
      name: 'Annualized volatility',
      nameLocation: 'middle',
      nameGap: 26,
      axisLine: { show: true, lineStyle: { color: c.axis } },
    },
    yAxis: { ...valueAxis(c, (v) => formatPercentTick(v)), name: 'CAGR', nameGap: 10 },
    series: [
      {
        type: 'scatter',
        name: 'Strategies',
        data: points.filter((p) => !p.benchmark).map(item),
        symbolSize: 11,
        color: c.series[0],
        itemStyle: { borderColor: c.surface, borderWidth: 2, opacity: 0.95 },
        label,
        labelLayout: { hideOverlap: true, moveOverlap: 'shiftY' },
        emphasis: { scale: 1.3, label: { show: true, color: c.ink } },
      },
      {
        type: 'scatter',
        name: 'Buy and Hold',
        data: points.filter((p) => p.benchmark).map(item),
        symbol: 'diamond',
        symbolSize: 14,
        color: c.reference,
        itemStyle: { borderColor: c.surface, borderWidth: 2 },
        label: { ...label, color: c.ink },
        z: 4,
      },
    ],
  }
}

export function drawdownBars(c: ChartColors, points: StrategyPoint[]): ChartOption {
  const sorted = [...points].sort((a, b) => b.maxDrawdown - a.maxDrawdown)
  const chrome = axisChrome(c)
  return {
    grid: { left: 4, right: 48, top: 4, bottom: 4, containLabel: true },
    tooltip: {
      trigger: 'item',
      ...tooltipBox(c),
      formatter: (raw: unknown) => {
        const p = raw as { name: string; value: number; color: string }
        return tooltipHeader(p.name) + tooltipRow(p.color, formatPercent(-p.value), 'max drawdown')
      },
    },
    // Bars show drawdown depth from a zero baseline; labels keep the signed value.
    xAxis: {
      ...valueAxis(c, (v) => formatPercent(-v, 0)),
      scale: false,
      min: 0,
      axisLabel: { show: false },
    },
    yAxis: {
      type: 'category',
      data: sorted.map((p) => p.name),
      inverse: true,
      ...chrome,
      axisLine: { show: false },
      splitLine: { show: false },
      axisLabel: { ...chrome.axisLabel, color: c.ink2 },
    },
    series: [
      {
        type: 'bar',
        data: sorted.map((p) => ({
          value: -p.maxDrawdown,
          itemStyle: { color: p.benchmark ? c.reference : c.series[0], borderRadius: [0, 4, 4, 0] },
        })),
        barMaxWidth: 14,
        label: {
          show: true,
          position: 'right',
          distance: 4,
          color: c.muted,
          fontSize: 10.5,
          formatter: (raw: unknown) => formatPercent(-(raw as { value: number }).value),
        },
      },
    ],
  }
}
