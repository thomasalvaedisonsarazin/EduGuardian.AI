import { useMemo } from 'react'
import { cn } from '@/lib/cn'
import type { ImportBatchDetail } from '@/types/imports'
import { cellIssueIndex } from './labels'

const highlight = {
  error: 'bg-rose-100 text-rose-800 ring-1 ring-inset ring-rose-300 dark:bg-rose-900/40 dark:text-rose-200',
  warning: 'bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200',
} as const

/** Normalized preview rows with problem cells highlighted. */
export function PreviewTable({ batch }: { batch: ImportBatchDetail }) {
  const index = useMemo(() => cellIssueIndex(batch.issues), [batch.issues])
  const subjectHeaders = batch.headers.filter((h) => batch.column_map.subjects[h] != null)
  const admissionColumn = batch.column_map.admission_column ?? ''
  const subjectName = (header: string): string | undefined =>
    batch.exam_subjects.find((s) => s.id === batch.column_map.subjects[header])?.name

  if (batch.preview.length === 0) {
    return (
      <p className="text-sm text-slate-500 dark:text-slate-400">
        No rows to preview — map the admission-number column first.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white/80 dark:border-slate-800 dark:bg-slate-900/60">
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        <caption className="sr-only">Preview of imported marks</caption>
        <thead className="bg-slate-50/80 dark:bg-slate-900">
          <tr className="text-xs font-semibold tracking-wide text-slate-500 uppercase dark:text-slate-400">
            <th scope="col" className="px-3 py-2 text-right">
              Row
            </th>
            <th scope="col" className="px-3 py-2 text-left">
              {admissionColumn || 'Admission no'}
            </th>
            {subjectHeaders.map((h) => {
              const name = subjectName(h)
              return (
                <th key={h} scope="col" className="px-3 py-2 text-right">
                  {h}
                  {name && name !== h && <span className="block font-normal normal-case text-slate-400">{name}</span>}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {batch.preview.map((row) => {
            const admissionSeverity = index.get(`${row.row}|${admissionColumn}`)
            return (
              <tr key={row.row}>
                <td className="px-3 py-2 text-right text-slate-400">{row.row}</td>
                <td
                  data-severity={admissionSeverity}
                  className={cn(
                    'px-3 py-2 font-medium text-slate-800 dark:text-slate-100',
                    admissionSeverity && highlight[admissionSeverity],
                  )}
                >
                  {row.admission_no || '—'}
                </td>
                {subjectHeaders.map((h) => {
                  const cell = row.marks[h]
                  const severity = index.get(`${row.row}|${h}`)
                  return (
                    <td
                      key={h}
                      data-severity={severity}
                      className={cn(
                        'px-3 py-2 text-right text-slate-700 tabular-nums dark:text-slate-200',
                        severity && highlight[severity],
                      )}
                    >
                      {cell ? (cell.is_absent ? 'AB' : cell.raw || '—') : '—'}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
      {batch.row_count > batch.preview.length && (
        <p className="px-3 py-2 text-xs text-slate-500">
          Showing the first {batch.preview.length} of {batch.row_count} rows.
        </p>
      )}
    </div>
  )
}
