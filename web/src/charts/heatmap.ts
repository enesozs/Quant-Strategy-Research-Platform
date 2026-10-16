import type { Heatmap } from '@/api/types'
import { formatParameterValue, humanize, isNum, type ParamFormat } from '@/lib/format'
import type { ChartColors } from '@/theme/chart'
import {
  axisChrome,
  escapeHtml,
  tooltipBox,
  tooltipHeader,
  tooltipRow,
  type ChartOption,
} from './base'

export function heatmapChart(
  c: ChartColors,
  heatmap: Heatmap,
  options: {
    format: (value: number) => string
    higherIsBetter: boolean
    objectiveLabel: string
    best?: { x: number | undefined; y: number | undefined }
    specs?: Record<string, ParamFormat>
  },
): ChartOption {
  const { x_values: xs, y_values: ys, z } = heatmap
  const values: number[] = []
  const data: Array<{
    value: [number, number, number | null]
    itemStyle?: object
    label?: object
  }> = []
  ys.forEach((yValue, yi) => {
    xs.forEach((xValue, xi) => {
      const v = z[yi]?.[xi]
      if (isNum(v)) values.push(v)
      const isBest = options.best?.x === xValue && options.best?.y === yValue
      data.push({
        value: [xi, yi, isNum(v) ? v : null],
        itemStyle: isBest ? { borderColor: c.ink, borderWidth: 2 } : undefined,
        ...(isBest
          ? {
              label: {
                show: true,
                formatter: '★',
                color: '#ffffff',
                fontSize: 13,
                textBorderColor: 'rgba(0,0,0,0.65)',
                textBorderWidth: 2,
              },
            }
          : {}),
      })
    })
  })
  const min = values.length ? Math.min(...values) : 0
  const max = values.length ? Math.max(...values) : 1
  const ramp = options.higherIsBetter ? [...c.sequential] : [...c.sequential].reverse()
  const xSpec = options.specs?.[heatmap.x_parameter]
  const ySpec = options.specs?.[heatmap.y_parameter]
  const chrome = axisChrome(c)
  const dense = xs.length > 14

  return {
    grid: { left: 4, right: 12, top: 8, bottom: 52, containLabel: true },
    tooltip: {
      trigger: 'item',
      ...tooltipBox(c),
      formatter: (raw: unknown) => {
        const p = raw as { value: [number, number, number | null] }
        const [xi, yi, v] = p.value
        return (
          tooltipHeader(
            `${humanize(heatmap.x_parameter)} ${formatParameterValue(xs[xi], xSpec)} · ` +
              `${humanize(heatmap.y_parameter)} ${formatParameterValue(ys[yi], ySpec)}`,
          ) +
          tooltipRow(
            c.series[0],
            isNum(v) ? options.format(v) : 'invalid',
            escapeHtml(`best ${options.objectiveLabel}`),
          )
        )
      },
    },
    xAxis: {
      type: 'category',
      data: xs.map((v) => formatParameterValue(v, xSpec)),
      name: humanize(heatmap.x_parameter),
      nameLocation: 'middle',
      nameGap: 26,
      ...chrome,
      splitLine: { show: false },
      axisLabel: { ...chrome.axisLabel, interval: dense ? 'auto' : 0, hideOverlap: true },
    },
    yAxis: {
      type: 'category',
      data: ys.map((v) => formatParameterValue(v, ySpec)),
      name: humanize(heatmap.y_parameter),
      nameLocation: 'middle',
      nameGap: 40,
      ...chrome,
      splitLine: { show: false },
    },
    visualMap: {
      min,
      max: max === min ? min + 1e-9 : max,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 10,
      itemHeight: 140,
      text: options.higherIsBetter ? ['better', 'worse'] : ['worse', 'better'],
      textGap: 8,
      textStyle: { color: c.muted, fontSize: 11 },
      inRange: { color: ramp },
      formatter: (value: unknown) => (typeof value === 'number' ? options.format(value) : ''),
    },
    series: [
      {
        type: 'heatmap',
        data,
        itemStyle: { borderColor: c.surface, borderWidth: 2, borderRadius: 2 },
        emphasis: { itemStyle: { borderColor: c.ink, borderWidth: 1 } },
      },
    ],
  }
}
