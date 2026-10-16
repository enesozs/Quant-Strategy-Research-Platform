// Shared chart chrome and tooltip helpers. Every builder takes ChartColors so charts re-theme.

import type { ComposeOption } from 'echarts/core'
import type {
  BarSeriesOption,
  HeatmapSeriesOption,
  LineSeriesOption,
  ScatterSeriesOption,
} from 'echarts/charts'
import type {
  GridComponentOption,
  LegendComponentOption,
  MarkAreaComponentOption,
  MarkLineComponentOption,
  MarkPointComponentOption,
  TooltipComponentOption,
  VisualMapComponentOption,
} from 'echarts/components'
import type { ChartColors } from '@/theme/chart'

export type ChartOption = ComposeOption<
  | BarSeriesOption
  | HeatmapSeriesOption
  | LineSeriesOption
  | ScatterSeriesOption
  | GridComponentOption
  | LegendComponentOption
  | MarkAreaComponentOption
  | MarkLineComponentOption
  | MarkPointComponentOption
  | TooltipComponentOption
  | VisualMapComponentOption
>

export const FONT = "'Inter Variable', ui-sans-serif, system-ui, sans-serif"
export const MONO = "'JetBrains Mono Variable', ui-monospace, monospace"

export function escapeHtml(text: string): string {
  return text.replace(
    /[&<>"']/g,
    (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch] ?? ch,
  )
}

export function axisChrome(c: ChartColors) {
  return {
    axisLine: { show: true, onZero: false, lineStyle: { color: c.axis } },
    axisTick: { show: false },
    axisLabel: { color: c.muted, fontSize: 11, fontFamily: FONT },
    splitLine: { show: true, lineStyle: { color: c.grid, type: 'solid' as const, width: 1 } },
    nameTextStyle: { color: c.muted, fontSize: 11, fontFamily: FONT },
  }
}

export function timeAxis(c: ChartColors, extra: Record<string, unknown> = {}) {
  const chrome = axisChrome(c)
  return {
    type: 'time' as const,
    ...chrome,
    splitLine: { show: false },
    axisLabel: {
      ...chrome.axisLabel,
      hideOverlap: true,
      formatter: { year: '{yyyy}', month: '{MMM}', day: '{MMM} {d}' },
    },
    axisPointer: { label: { show: false } },
    ...extra,
  }
}

export function valueAxis(
  c: ChartColors,
  format: (value: number) => string,
  extra: Record<string, unknown> = {},
) {
  const chrome = axisChrome(c)
  return {
    type: 'value' as const,
    scale: true,
    ...chrome,
    axisLine: { show: false },
    axisLabel: { ...chrome.axisLabel, formatter: (value: number) => format(value) },
    splitNumber: 4,
    ...extra,
  }
}

export function legend(c: ChartColors, extra: Record<string, unknown> = {}) {
  return {
    top: 0,
    left: 0,
    type: 'scroll' as const,
    icon: 'roundRect',
    itemWidth: 14,
    itemHeight: 3,
    itemGap: 16,
    textStyle: { color: c.ink2, fontSize: 12, fontFamily: FONT },
    pageIconColor: c.ink2,
    pageTextStyle: { color: c.muted },
    inactiveColor: c.axis,
    ...extra,
  }
}

export function tooltipBox(c: ChartColors) {
  return {
    backgroundColor: c.tooltip,
    borderColor: c.tooltipBorder,
    borderWidth: 1,
    padding: [8, 10] as [number, number],
    textStyle: { color: c.ink, fontFamily: FONT, fontSize: 12 },
    extraCssText: 'border-radius: 8px; box-shadow: 0 6px 20px rgba(0,0,0,0.14);',
    confine: true,
  }
}

/** One tooltip row: value first (strong), series name second, keyed by a short line stroke. */
export function tooltipRow(color: string, value: string, name: string): string {
  return (
    `<div style="display:flex;align-items:center;gap:8px;line-height:20px">` +
    `<span style="display:inline-block;width:12px;height:2px;border-radius:1px;background:${color}"></span>` +
    `<span style="font-weight:600;font-variant-numeric:tabular-nums;font-family:${MONO};font-size:11.5px">${escapeHtml(value)}</span>` +
    `<span style="opacity:.72">${escapeHtml(name)}</span></div>`
  )
}

export function tooltipHeader(text: string): string {
  return `<div style="opacity:.66;margin-bottom:3px;font-size:11px">${escapeHtml(text)}</div>`
}

interface AxisParam {
  seriesName?: string
  color?: unknown
  value?: unknown
  axisValue?: unknown
  axisValueLabel?: string
  seriesType?: string
}

/** Crosshair tooltip listing every line at the hovered date. */
export function axisTooltip(
  c: ChartColors,
  format: (value: number, seriesName: string) => string,
  options: { skip?: (seriesName: string) => boolean } = {},
) {
  return {
    trigger: 'axis' as const,
    ...tooltipBox(c),
    axisPointer: { type: 'line' as const, lineStyle: { color: c.muted, width: 1 } },
    formatter: (raw: unknown) => {
      const params = (Array.isArray(raw) ? raw : [raw]) as AxisParam[]
      if (!params.length) return ''
      const first = params[0]
      const date = Array.isArray(first.value) ? String(first.value[0]) : String(first.axisValue)
      let html = tooltipHeader(formatTooltipDate(date))
      for (const p of params) {
        const name = p.seriesName ?? ''
        if (options.skip?.(name) || p.seriesType === 'scatter') continue
        const y = Array.isArray(p.value) ? p.value[1] : p.value
        if (typeof y !== 'number' || !Number.isFinite(y)) continue
        html += tooltipRow(typeof p.color === 'string' ? p.color : c.ink, format(y, name), name)
      }
      return html
    },
  }
}

export function formatTooltipDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (!match) {
    const parsed = new Date(Number(value))
    if (!Number.isNaN(parsed.getTime())) return parsed.toISOString().slice(0, 10)
    return value
  }
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ]
  return `${months[Number(match[2]) - 1]} ${Number(match[3])}, ${match[1]}`
}

/** Plot area: room for the legend on top, labels contained. */
export function grid(extra: Record<string, unknown> = {}) {
  return { left: 4, right: 12, top: 34, bottom: 4, containLabel: true, ...extra }
}
