import type { ProfilePoint } from '@/api/types'
import { formatParameterValue, humanize, type ParamFormat } from '@/lib/format'
import type { ChartColors } from '@/theme/chart'
import {
  axisChrome,
  legend,
  tooltipBox,
  tooltipHeader,
  tooltipRow,
  valueAxis,
  type ChartOption,
} from './base'

/** Objective as a function of one parameter: best and median over the other parameters. */
export function profileChart(
  c: ChartColors,
  parameter: string,
  points: ProfilePoint[],
  options: {
    format: (value: number) => string
    selected?: number
    spec?: ParamFormat
  },
): ChartOption {
  const labels = points.map((p) => formatParameterValue(p.value, options.spec))
  const selectedIndex = points.findIndex((p) => p.value === options.selected)
  const chrome = axisChrome(c)
  return {
    grid: { left: 4, right: 12, top: 44, bottom: 28, containLabel: true },
    legend: legend(c),
    tooltip: {
      trigger: 'axis',
      ...tooltipBox(c),
      axisPointer: { type: 'line', lineStyle: { color: c.muted, width: 1 } },
      formatter: (raw: unknown) => {
        const params = raw as Array<{
          dataIndex: number
          seriesName: string
          color: string
          value: number | null
        }>
        if (!params.length) return ''
        let html = tooltipHeader(`${humanize(parameter)} = ${labels[params[0].dataIndex]}`)
        for (const p of params)
          if (typeof p.value === 'number')
            html += tooltipRow(p.color, options.format(p.value), p.seriesName)
        return html
      },
    },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: false,
      name: humanize(parameter),
      nameLocation: 'middle',
      nameGap: 24,
      ...chrome,
      splitLine: { show: false },
      axisLabel: { ...chrome.axisLabel, hideOverlap: true },
    },
    yAxis: valueAxis(c, options.format, { splitNumber: 3 }),
    series: [
      {
        type: 'line',
        name: 'Best',
        data: points.map((p) => p.best),
        color: c.series[0],
        lineStyle: { width: 2, color: c.series[0] },
        symbol: 'circle',
        symbolSize: 7,
        itemStyle: { borderColor: c.surface, borderWidth: 2 },
        markLine:
          selectedIndex >= 0
            ? {
                silent: true,
                symbol: 'none',
                lineStyle: { color: c.axis, type: 'solid', width: 1 },
                label: {
                  formatter: 'optimum',
                  color: c.muted,
                  fontSize: 10,
                  position: 'end',
                },
                data: [{ xAxis: selectedIndex }],
              }
            : undefined,
      },
      {
        type: 'line',
        name: 'Median',
        data: points.map((p) => p.median),
        color: c.reference,
        lineStyle: { width: 2, color: c.reference },
        symbol: 'circle',
        symbolSize: 6,
        itemStyle: { borderColor: c.surface, borderWidth: 2 },
      },
    ],
  }
}
