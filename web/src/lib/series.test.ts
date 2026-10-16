import { describe, expect, it } from 'vitest'
import {
  extent,
  lastFinite,
  nonEmptyColumns,
  rebase,
  segments,
  toPoints,
  valueAtDate,
} from './series'

const dates = ['2020-01-01', '2020-01-02', '2020-01-03', '2020-01-06', '2020-01-07']

describe('series helpers', () => {
  it('zips points and turns non-finite values into gaps', () => {
    expect(toPoints(dates.slice(0, 3), [1, null, 3])).toEqual([
      ['2020-01-01', 1],
      ['2020-01-02', null],
      ['2020-01-03', 3],
    ])
    expect(toPoints(dates, undefined)).toEqual([])
  })

  it('finds contiguous active segments', () => {
    expect(segments(dates, [0, 1, 1, 0, 0.5])).toEqual([
      ['2020-01-02', '2020-01-03'],
      ['2020-01-07', '2020-01-07'],
    ])
    expect(segments(dates, [1, 1, 1, 1, 1])).toEqual([['2020-01-01', '2020-01-07']])
    expect(segments(dates, [-1, 0, 0, 0, -1], (v) => v < 0)).toHaveLength(2)
  })

  it('rebases to the first finite value', () => {
    expect(rebase([null, 2, 4, null])).toEqual([null, 1, 2, null])
    expect(rebase([0, 1])).toEqual([null, null])
  })

  it('computes extents and last values', () => {
    expect(extent([3, null, -1, 2])).toEqual([-1, 3])
    expect(extent([null])).toBeNull()
    expect(lastFinite([1, 2, null])).toBe(2)
  })

  it('looks values up by date', () => {
    const at = valueAtDate(dates, [10, 11, 12, 13, null])
    expect(at('2020-01-03')).toBe(12)
    expect(at('2020-01-07')).toBeNull()
    expect(at('2021-01-01')).toBeNull()
  })

  it('lists non-empty columns', () => {
    expect(nonEmptyColumns({ dates: ['a'], columns: { a: [1], b: [null] } })).toEqual(['a'])
  })
})

describe('drawdown', () => {
  it('measures distance from the running peak', async () => {
    const { drawdown } = await import('./series')
    expect(drawdown([100, 120, 90, null, 130])).toEqual([0, 0, -0.25, null, 0])
  })
})
