import { motion } from 'framer-motion'
import type { Key, ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { EmptyState } from './EmptyState'
import { Spinner } from './Spinner'

export interface DataTableColumn<T> {
  /** Unique column id. */
  id: string
  header: ReactNode
  cell: (row: T, index: number) => ReactNode
  align?: 'left' | 'center' | 'right'
  className?: string
  headerClassName?: string
}

export interface DataTableProps<T> {
  columns: readonly DataTableColumn<T>[]
  rows: readonly T[]
  getRowId: (row: T, index: number) => Key
  loading?: boolean
  onRowClick?: (row: T) => void
  /** Rendered instead of the body when there are no rows. */
  empty?: ReactNode
  caption?: string
  className?: string
  dense?: boolean
}

const alignClass = { left: 'text-left', center: 'text-center', right: 'text-right' } as const

export function DataTable<T>({
  columns,
  rows,
  getRowId,
  loading = false,
  onRowClick,
  empty,
  caption,
  className,
  dense = false,
}: DataTableProps<T>) {
  const cellPad = dense ? 'px-3 py-2' : 'px-4 py-3'

  return (
    <div
      className={cn(
        'overflow-x-auto rounded-2xl border border-slate-200 bg-white/80 dark:border-slate-800 dark:bg-slate-900/60',
        className,
      )}
    >
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="bg-slate-50/80 dark:bg-slate-900">
          <tr>
            {columns.map((col) => (
              <th
                key={col.id}
                scope="col"
                className={cn(
                  cellPad,
                  'text-xs font-semibold tracking-wide text-slate-500 uppercase dark:text-slate-400',
                  alignClass[col.align ?? 'left'],
                  col.headerClassName,
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {loading ? (
            <tr>
              <td colSpan={columns.length} className="py-10 text-center">
                <Spinner showLabel label="Loading data" />
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length}>{empty ?? <EmptyState title="No records yet" />}</td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <motion.tr
                key={getRowId(row, i)}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2, delay: Math.min(i * 0.02, 0.3) }}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={cn(
                  'transition-colors hover:bg-brand-50/50 dark:hover:bg-slate-800/60',
                  onRowClick && 'cursor-pointer',
                )}
              >
                {columns.map((col) => (
                  <td
                    key={col.id}
                    className={cn(cellPad, 'text-slate-700 dark:text-slate-200', alignClass[col.align ?? 'left'], col.className)}
                  >
                    {col.cell(row, i)}
                  </td>
                ))}
              </motion.tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
