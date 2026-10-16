// Thin typed ECharts wrapper (tree-shaken build). Options are rebuilt from the active palette,
// so a theme toggle re-renders every chart with notMerge.

import { BarChart, HeatmapChart, LineChart, ScatterChart } from 'echarts/charts'
import {
  AxisPointerComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import clsx from 'clsx'
import { useEffect, useRef } from 'react'
import type { ChartOption } from './base'

echarts.use([
  BarChart,
  HeatmapChart,
  LineChart,
  ScatterChart,
  AxisPointerComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
])

interface EChartProps {
  option: ChartOption
  /** Describes the chart for screen readers; the canvas itself is opaque to them. */
  ariaLabel: string
  /** Total height including axis labels (px). */
  height?: number
  className?: string
}

export function EChart({ option, ariaLabel, height = 300, className }: EChartProps) {
  const container = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    const element = container.current
    if (!element) return
    const instance = echarts.init(element, undefined, { renderer: 'canvas' })
    chart.current = instance
    let frame = 0
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => instance.resize())
    })
    observer.observe(element)
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      instance.dispose()
      chart.current = null
    }
  }, [])

  useEffect(() => {
    chart.current?.setOption({ animationDuration: 350, ...option }, { notMerge: true })
  }, [option])

  return (
    <div
      ref={container}
      role="img"
      aria-label={ariaLabel}
      className={clsx('w-full min-w-0', className)}
      style={{ height }}
    />
  )
}
