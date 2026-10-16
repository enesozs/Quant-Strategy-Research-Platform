// Chart palette (dataviz reference palette, validated with scripts/validate_palette.js against
// this app's card surfaces: light #ffffff, dark #17181a; all 8 adjacent pairs pass CVD and
// normal-vision checks in both modes). Light slots 3-5 are below 3:1 on white, so charts that
// use them keep a legend and a table twin.
//
// Roles: the strategy under study is slot 1 (the UI accent family); Buy and Hold and other
// references are a neutral grey so the eye goes to the strategy; categorical slots are assigned
// in fixed order and follow the entity, never its rank.

import { useTheme, type Theme } from './theme'

const PALETTE = {
  light: {
    series: [
      '#2a78d6',
      '#eb6834',
      '#1baf7a',
      '#eda100',
      '#e87ba4',
      '#008300',
      '#6250d6',
      '#e34948',
    ],
    reference: '#8a8882',
    /** Sequential blue ramp, light → dark (heatmaps). */
    sequential: ['#e3eefc', '#b7d3f6', '#86b6ef', '#5598e7', '#2a78d6', '#1c5cab', '#0d366b'],
    pos: '#0b7a32',
    neg: '#c03535',
    negFill: 'rgba(192, 53, 53, 0.10)',
    band: 'rgba(42, 120, 214, 0.07)',
    ink: '#141413',
    ink2: '#4c4b47',
    muted: '#76746e',
    grid: '#ebeae5',
    axis: '#cfcec7',
    surface: '#ffffff',
    tooltip: '#ffffff',
    tooltipBorder: 'rgba(20, 20, 19, 0.10)',
  },
  dark: {
    series: [
      '#3987e5',
      '#d95926',
      '#199e70',
      '#c98500',
      '#d55181',
      '#008300',
      '#9085e9',
      '#e66767',
    ],
    reference: '#7f7e79',
    sequential: ['#1d2a3b', '#184f95', '#256abf', '#3987e5', '#6da7ec', '#9ec5f4', '#cde2fb'],
    pos: '#3fbf6e',
    neg: '#f07474',
    negFill: 'rgba(240, 116, 116, 0.12)',
    band: 'rgba(57, 135, 229, 0.10)',
    ink: '#ecebe7',
    ink2: '#b8b7b1',
    muted: '#8d8c86',
    grid: '#232529',
    axis: '#363940',
    surface: '#16171a',
    tooltip: '#1f2024',
    tooltipBorder: 'rgba(255, 255, 255, 0.10)',
  },
} as const

export interface ChartColors {
  series: readonly string[]
  reference: string
  sequential: readonly string[]
  pos: string
  neg: string
  negFill: string
  band: string
  ink: string
  ink2: string
  muted: string
  grid: string
  axis: string
  surface: string
  tooltip: string
  tooltipBorder: string
}

export function chartColors(theme: Theme): ChartColors {
  return PALETTE[theme]
}

export function useChartColors(): ChartColors {
  return PALETTE[useTheme().theme]
}

/** Fixed colors for the validation parameter sets, shared by split and walk-forward charts. */
export function parameterSetColor(c: ChartColors, label: string, index: number): string {
  const l = label.toLowerCase()
  if (l.includes('buy') || l.includes('hold') || l.includes('benchmark')) return c.reference
  if (l.includes('raw')) return c.series[0]
  if (l.includes('robust')) return c.series[1]
  if (l.includes('default')) return c.series[2]
  return c.series[(index + 3) % c.series.length]
}
