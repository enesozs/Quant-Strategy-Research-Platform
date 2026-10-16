import type { Num } from '@/api/types'
import { toPoints } from '@/lib/series'
import type { ChartColors } from '@/theme/chart'
import { axisTooltip, grid, legend, timeAxis, valueAxis, type ChartOption } from './base'

export interface LineSpec {
  name: string
  values: readonly Num[]
  color: string
  width?: number
  /** Fill under the line with a ~10% wash of the series color. */
  area?: boolean
  dashed?: boolean
  step?: boolean
}

export interface TimeLinesConfig {
  dates: string[]
  lines: LineSpec[]
  /** Axis tick and tooltip formatting. */
  format: (value: number) => string
  axisFormat?: (value: number) => string
  /** Shaded date ranges (e.g. periods in the market). */
  shaded?: Array<[string, string]>
  shadeColor?: string
  /** Horizontal reference line (e.g. initial capital, zero). */
  reference?: { value: number; label?: string }
  /** Force the y-axis to end at zero (drawdowns). */
  maxZero?: boolean
  showLegend?: boolean
}

export function timeLines(c: ChartColors, config: TimeLinesConfig): ChartOption {
  const { dates, lines, format } = config
  const showLegend = config.showLegend ?? lines.length > 1
  return {
    grid: grid({ top: showLegend ? 34 : 12 }),
    legend: showLegend ? legend(c) : { show: false },
    tooltip: axisTooltip(c, format),
    xAxis: timeAxis(c),
    yAxis: valueAxis(c, config.axisFormat ?? format, config.maxZero ? { max: 0 } : {}),
    series: lines.map((line, index) => ({
      type: 'line' as const,
      name: line.name,
      data: toPoints(dates, line.values),
      showSymbol: false,
      symbol: 'circle',
      symbolSize: 8,
      sampling: 'lttb' as const,
      step: line.step ? ('end' as const) : undefined,
      z: lines.length - index + 2,
      color: line.color,
      lineStyle: {
        width: line.width ?? 2,
        color: line.color,
        type: line.dashed ? ('dashed' as const) : ('solid' as const),
        cap: 'round' as const,
        join: 'round' as const,
      },
      areaStyle: line.area ? { color: line.color, opacity: 0.1 } : undefined,
      emphasis: { focus: 'none' as const, lineStyle: { width: line.width ?? 2 } },
      markArea:
        index === 0 && config.shaded?.length
          ? {
              silent: true,
              itemStyle: { color: config.shadeColor ?? c.band },
              data: config.shaded.map(([start, end]) => [{ xAxis: start }, { xAxis: end }]),
            }
          : undefined,
      markLine:
        index === 0 && config.reference
          ? {
              silent: true,
              symbol: 'none',
              lineStyle: { color: c.axis, type: 'solid' as const, width: 1 },
              label: config.reference.label
                ? {
                    formatter: config.reference.label,
                    color: c.muted,
                    fontSize: 10,
                    position: 'insideStartTop' as const,
                  }
                : { show: false },
              data: [{ yAxis: config.reference.value }],
            }
          : undefined,
    })),
  }
}
