// Compact sortable table for API rows: sticky header, per-column number formatting, optional
// row highlighting and click-through. Scrolls inside its own container on narrow screens.

import clsx from 'clsx'
import { useMemo, useState, type ReactNode } from 'react'
import type { Row } from '@/api/types'
import { columnLabel, inferKind } from '@/lib/columns'
import { formatValue, isNumericKind, type ValueKind } from '@/lib/format'
import { Icon } from './Icon'

type Cell = Row[string]

export interface Column {
  key: string
  label?: ReactNode
  kind?: ValueKind
  /** Custom cell renderer; sorting still uses the raw value unless sortValue is given. */
  render?: (row: Row) => ReactNode
  sortValue?: (row: Row) => number | string | null
  align?: 'left' | 'right'
  title?: string
  /** Emphasize this column (e.g. the Bonferroni p-value). */
  highlight?: boolean
  className?: string
}

export type RowTone = 'best' | 'worst' | 'reference' | undefined

interface DataTableProps {
  rows: Row[]
  columns?: Column[]
  /** Hide these keys when columns are inferred. */
  hide?: string[]
  /** Units for *_objective columns. */
  objectiveFormat?: 'percent' | 'ratio'
  rowTone?: (row: Row, index: number) => RowTone
  onRowClick?: (row: Row) => void
  rowActionLabel?: (row: Row) => string
  initialSort?: { key: string; direction: 'asc' | 'desc' }
  maxHeight?: number
  caption: string
  emptyText?: string
  className?: string
}

function compare(a: Cell | number | string | null, b: Cell | number | string | null): number {
  const aNull = a === null || a === undefined || (typeof a === 'number' && !Number.isFinite(a))
  const bNull = b === null || b === undefined || (typeof b === 'number' && !Number.isFinite(b))
  if (aNull || bNull) return aNull === bNull ? 0 : aNull ? 1 : -1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  if (typeof a === 'boolean' && typeof b === 'boolean') return Number(a) - Number(b)
  return String(a).localeCompare(String(b), undefined, { numeric: true })
}

export function DataTable({
  rows,
  columns,
  hide = [],
  objectiveFormat,
  rowTone,
  onRowClick,
  rowActionLabel,
  initialSort,
  maxHeight = 440,
  caption,
  emptyText = 'No rows.',
  className,
}: DataTableProps) {
  const [sort, setSort] = useState(initialSort ?? null)

  const resolved = useMemo<Array<Column & { kind: ValueKind }>>(() => {
    const base: Column[] =
      columns ??
      [...new Set(rows.flatMap((row) => Object.keys(row)))]
        .filter((key) => !hide.includes(key))
        .map((key) => ({ key }))
    return base.map((column) => {
      const sample = rows.find(
        (row) => row[column.key] !== null && row[column.key] !== undefined,
      )?.[column.key]
      return {
        ...column,
        kind:
          column.kind ?? (column.render ? 'text' : inferKind(column.key, sample, objectiveFormat)),
      }
    })
  }, [columns, rows, hide, objectiveFormat])

  const sorted = useMemo(() => {
    const indexed = rows.map((row, index) => ({ row, index }))
    if (!sort) return indexed
    const column = resolved.find((c) => c.key === sort.key)
    const value = (row: Row) => (column?.sortValue ? column.sortValue(row) : row[sort.key])
    const sign = sort.direction === 'asc' ? 1 : -1
    return indexed.sort((a, b) => {
      const result = compare(value(a.row), value(b.row))
      // Nulls always last, regardless of direction.
      const aNull = value(a.row) === null || value(a.row) === undefined
      const bNull = value(b.row) === null || value(b.row) === undefined
      if (aNull !== bNull) return aNull ? 1 : -1
      return result * sign
    })
  }, [rows, sort, resolved])

  const toggleSort = (key: string, numeric: boolean) =>
    setSort((current) =>
      current?.key === key
        ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: numeric ? 'desc' : 'asc' },
    )

  if (!rows.length) return <p className="py-6 text-center text-sm text-muted">{emptyText}</p>

  return (
    <div
      className={clsx(
        'scrollbar-thin relative overflow-auto rounded-lg border border-line',
        className,
      )}
      style={{ maxHeight }}
      tabIndex={0}
      aria-label={caption}
      role="region"
    >
      <table className="w-full border-separate border-spacing-0 text-[13px]">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {resolved.map((column) => {
              const numeric = isNumericKind(column.kind)
              const align = column.align ?? (numeric ? 'right' : 'left')
              const active = sort?.key === column.key
              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={
                    active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'
                  }
                  className={clsx(
                    'sticky top-0 z-10 border-b border-line bg-surface-2 px-0 py-0 text-xs font-medium whitespace-nowrap text-muted',
                    column.highlight && 'text-ink',
                  )}
                >
                  <button
                    type="button"
                    title={column.title}
                    onClick={() => toggleSort(column.key, numeric)}
                    className={clsx(
                      'flex w-full items-center gap-1 px-3 py-2 hover:text-ink',
                      align === 'right' ? 'justify-end text-right' : 'justify-start text-left',
                      active && 'text-ink',
                    )}
                  >
                    {column.label ?? columnLabel(column.key)}
                    <Icon
                      name={
                        active ? (sort.direction === 'asc' ? 'chevronUp' : 'chevronDown') : 'sort'
                      }
                      size={12}
                      className={clsx('shrink-0', active ? 'opacity-90' : 'opacity-30')}
                    />
                  </button>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map(({ row, index }) => {
            const tone = rowTone?.(row, index)
            const clickable = !!onRowClick
            return (
              <tr
                key={index}
                onClick={clickable ? () => onRowClick(row) : undefined}
                onKeyDown={
                  clickable
                    ? (event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          onRowClick(row)
                        }
                      }
                    : undefined
                }
                tabIndex={clickable ? 0 : undefined}
                aria-label={clickable ? rowActionLabel?.(row) : undefined}
                className={clsx(
                  'group',
                  clickable && 'cursor-pointer',
                  tone === 'best' && 'bg-accent-soft',
                  tone === 'worst' && 'bg-neg-soft',
                  tone === 'reference' && 'bg-surface-2/60',
                )}
              >
                {resolved.map((column, ci) => {
                  const numeric = isNumericKind(column.kind)
                  const align = column.align ?? (numeric ? 'right' : 'left')
                  const raw = row[column.key]
                  return (
                    <td
                      key={column.key}
                      className={clsx(
                        'border-b border-line px-3 py-1.5 whitespace-nowrap group-last:border-b-0',
                        clickable && 'group-hover:bg-surface-2',
                        align === 'right' ? 'text-right' : 'text-left',
                        numeric || column.kind === 'date' ? 'num font-mono text-[12px]' : '',
                        column.highlight && 'font-semibold',
                        ci === 0 && tone === 'best' && 'shadow-[inset_2px_0_0_var(--accent)]',
                        ci === 0 && tone === 'worst' && 'shadow-[inset_2px_0_0_var(--neg)]',
                        tone === 'reference' ? 'text-ink-2' : 'text-ink',
                        column.className,
                      )}
                    >
                      {column.render ? column.render(row) : formatValue(column.kind, raw)}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
