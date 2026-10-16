import { describe, expect, it } from 'vitest'
import { inferKind } from './columns'
import { sameRequest, stableStringify } from './equal'
import {
  formatCurrency,
  formatDate,
  formatElapsed,
  formatMetric,
  formatMetricDelta,
  formatMultiple,
  formatParameterValue,
  formatPercent,
  formatPValue,
  formatRatio,
  formatSignedPercent,
  humanize,
} from './format'

describe('number formatting', () => {
  it('formats fractions as percentages with a typographic minus', () => {
    expect(formatPercent(0.1234)).toBe('12.3%')
    expect(formatPercent(-0.0567, 2)).toBe('−5.67%')
    expect(formatPercent(-0.00001)).toBe('0.0%')
    expect(formatPercent(null)).toBe('—')
    expect(formatPercent(Number.NaN)).toBe('—')
  })

  it('signs deltas', () => {
    expect(formatSignedPercent(0.05)).toBe('+5.0%')
    expect(formatSignedPercent(-0.05)).toBe('−5.0%')
    expect(formatSignedPercent(0)).toBe('0.0%')
    expect(formatMetricDelta('cagr', 0.031)).toBe('+3.1 pp')
    expect(formatMetricDelta('sharpe_ratio', -0.244)).toBe('−0.24')
  })

  it('formats ratios, money, multiples and p-values', () => {
    expect(formatRatio(1.23456)).toBe('1.23')
    expect(formatCurrency(12345.6)).toBe('$12,346')
    expect(formatCurrency(-500)).toBe('−$500')
    expect(formatCurrency(1_250_000, { compact: true })).toBe('$1.3M')
    expect(formatMultiple(12.34)).toBe('12.3×')
    expect(formatPValue(0.0004)).toBe('<0.001')
    expect(formatPValue(0.04567)).toBe('0.046')
  })

  it('formats metrics by key', () => {
    expect(formatMetric('max_drawdown', -0.2)).toBe('−20.0%')
    expect(formatMetric('calmar_ratio', 0.5)).toBe('0.50')
    expect(formatMetric('final_value', 10000)).toBe('$10,000')
  })

  it('formats parameters', () => {
    expect(formatParameterValue(20, { type: 'int' })).toBe('20')
    expect(formatParameterValue(0.15, { format: 'percent' })).toBe('15%')
    expect(formatParameterValue(0.025, { format: 'percent' })).toBe('2.5%')
    expect(formatParameterValue(1e-5)).toBe('0.00001')
  })
})

describe('dates and labels', () => {
  it('formats ISO dates without timezone drift', () => {
    expect(formatDate('2020-01-03')).toBe('Jan 3, 2020')
    expect(formatDate('2024-12-31T00:00:00')).toBe('Dec 31, 2024')
    expect(formatDate(null)).toBe('—')
  })

  it('formats elapsed time', () => {
    expect(formatElapsed(4200)).toBe('4s')
    expect(formatElapsed(65_000)).toBe('1m 05s')
  })

  it('humanizes keys', () => {
    expect(humanize('fast_window')).toBe('Fast window')
    expect(humanize('cagr_rank')).toBe('CAGR rank')
  })
})

describe('column kinds', () => {
  it('infers formats from column names', () => {
    expect(inferKind('total_return', 0.1)).toBe('percent')
    expect(inferKind('test_sharpe_ratio', 1)).toBe('ratio')
    expect(inferKind('sharpe_rank', 1)).toBe('integer')
    expect(inferKind('test_start', '2024-01-01')).toBe('date')
    expect(inferKind('bonferroni_pvalue', 0.2)).toBe('pvalue')
    expect(inferKind('raw_test_objective', 0.2, 'percent')).toBe('percent')
    expect(inferKind('stitched_final_value', 1)).toBe('currency')
    expect(inferKind('half_life_days', 12.5)).toBe('number')
    expect(inferKind('qualified', true)).toBe('boolean')
  })
})

describe('request equality', () => {
  it('ignores key order and undefined fields', () => {
    expect(stableStringify({ b: 1, a: { d: 1, c: 2 } })).toBe('{"a":{"c":2,"d":1},"b":1}')
    expect(sameRequest({ a: 1, b: undefined }, { a: 1 })).toBe(true)
    expect(sameRequest({ a: [1, 2] }, { a: [2, 1] })).toBe(false)
  })
})
