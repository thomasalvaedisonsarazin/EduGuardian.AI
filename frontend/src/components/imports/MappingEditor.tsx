import { RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Badge, GradientButton } from '@/components/ui'
import type { ID } from '@/types'
import type { ColumnMap, ExamSubject } from '@/types/imports'
import { selectClass } from './styles'

export interface MappingEditorProps {
  headers: readonly string[]
  initial: ColumnMap
  subjects: readonly ExamSubject[]
  saving?: boolean
  onSubmit: (mapping: ColumnMap) => void
}

const ADMISSION = '__admission__'
const IGNORE = ''

/** One select per file header: admission number, an exam subject, or ignored. */
export function MappingEditor({ headers, initial, subjects, saving = false, onSubmit }: MappingEditorProps) {
  const [choice, setChoice] = useState<Record<string, string>>(() => {
    const out: Record<string, string> = {}
    for (const h of headers) {
      if (h === initial.admission_column) out[h] = ADMISSION
      else {
        const sid = initial.subjects[h]
        out[h] = sid != null ? String(sid) : IGNORE
      }
    }
    return out
  })

  const setFor = (header: string, value: string) => {
    setChoice((prev) => {
      const next = { ...prev, [header]: value }
      // Admission column and each subject can be chosen only once: clear the previous holder.
      if (value !== IGNORE) {
        for (const h of headers) if (h !== header && next[h] === value) next[h] = IGNORE
      }
      return next
    })
  }

  const admissionColumn = headers.find((h) => choice[h] === ADMISSION) ?? null
  const mappedIds = new Set(Object.values(choice).filter((v) => v !== IGNORE && v !== ADMISSION))
  const unmappedSubjects = subjects.filter((s) => !mappedIds.has(String(s.id)))

  const submit = () => {
    const mapped: Record<string, ID | null> = {}
    for (const h of headers) {
      if (h === admissionColumn) continue
      const value = choice[h]
      mapped[h] = value && value !== IGNORE ? Number(value) : null
    }
    onSubmit({ admission_column: admissionColumn, subjects: mapped })
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
          <caption className="sr-only">Column mapping</caption>
          <thead className="bg-slate-50/80 text-xs font-semibold tracking-wide text-slate-500 uppercase dark:bg-slate-900 dark:text-slate-400">
            <tr>
              <th scope="col" className="px-4 py-2 text-left">
                Column in file
              </th>
              <th scope="col" className="px-4 py-2 text-left">
                Maps to
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white/80 dark:divide-slate-800 dark:bg-slate-900/60">
            {headers.map((h) => (
              <tr key={h}>
                <td className="px-4 py-2 font-medium text-slate-800 dark:text-slate-100">{h}</td>
                <td className="px-4 py-2">
                  <select
                    aria-label={`Mapping for ${h}`}
                    className={selectClass}
                    value={choice[h] ?? IGNORE}
                    onChange={(e) => setFor(h, e.target.value)}
                  >
                    <option value={IGNORE}>— Ignore —</option>
                    <option value={ADMISSION}>Admission number</option>
                    {subjects.map((s) => (
                      <option key={s.id} value={String(s.id)}>
                        {s.name} ({s.code}, max {String(s.max_marks)})
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {admissionColumn === null && <Badge tone="danger">Choose the admission-number column</Badge>}
        {unmappedSubjects.map((s) => (
          <Badge key={s.id} tone="warning">
            {s.name} has no column
          </Badge>
        ))}
      </div>
      <GradientButton icon={RefreshCw} loading={saving} onClick={submit}>
        Apply mapping &amp; re-validate
      </GradientButton>
    </div>
  )
}
