import { Save } from 'lucide-react'
import { useState } from 'react'
import { EmptyState, GradientButton, Spinner } from '@/components/ui'
import { useExamSubjects, useReplaceExamSubjects, useSubjects } from '@/hooks/useSetup'
import { cn } from '@/lib/cn'
import type { ID, Subject } from '@/types'
import type { ExamSubjectConfigDetail, ExamSubjectConfigInput } from '@/types/setup'
import { ErrorAlert } from './shared'

interface RowState {
  included: boolean
  max: string
  pass: string
}

type Draft = Record<ID, RowState>

function initialDraft(subjects: readonly Subject[], configs: readonly ExamSubjectConfigDetail[]): Draft {
  const bySubject = new Map(configs.map((c) => [c.subject_id, c]))
  const draft: Draft = {}
  for (const s of subjects) {
    const cfg = bySubject.get(s.id)
    draft[s.id] = cfg
      ? { included: true, max: String(Number(cfg.max_marks)), pass: String(Number(cfg.pass_marks)) }
      : { included: false, max: '100', pass: '35' }
  }
  return draft
}

function rowError(row: RowState): string | null {
  if (!row.included) return null
  const max = Number(row.max)
  const pass = Number(row.pass)
  if (row.max.trim() === '' || !Number.isFinite(max) || max <= 0) return 'Max must be greater than 0'
  if (row.pass.trim() === '' || !Number.isFinite(pass) || pass < 0) return 'Pass must be 0 or more'
  if (pass > max) return 'Pass marks cannot exceed max marks'
  return null
}

export interface ExamSubjectsEditorProps {
  examId: ID
  onDone?: () => void
}

/** Loads subjects + current configs, then renders the editable grid once both are ready. */
export function ExamSubjectsEditor({ examId, onDone }: ExamSubjectsEditorProps) {
  const subjects = useSubjects()
  const configs = useExamSubjects(examId)

  if (subjects.isLoading || configs.isLoading) return <Spinner showLabel label="Loading subjects" />
  if (subjects.error || configs.error) return <ErrorAlert error={subjects.error ?? configs.error} />
  if (!subjects.data?.length) {
    return <EmptyState title="No subjects" description="Create subjects in the Subjects tab first." />
  }
  return (
    <EditorGrid
      key={configs.dataUpdatedAt}
      examId={examId}
      subjects={subjects.data}
      configs={configs.data ?? []}
      onDone={onDone}
    />
  )
}

interface EditorGridProps {
  examId: ID
  subjects: Subject[]
  configs: ExamSubjectConfigDetail[]
  onDone?: () => void
}

function EditorGrid({ examId, subjects, configs, onDone }: EditorGridProps) {
  const [draft, setDraft] = useState<Draft>(() => initialDraft(subjects, configs))
  const [saved, setSaved] = useState(false)
  const replace = useReplaceExamSubjects(examId)
  const errors = subjects.map((s) => rowError(draft[s.id]))
  const hasErrors = errors.some((e) => e !== null)

  const update = (id: ID, patch: Partial<RowState>) => {
    setSaved(false)
    setDraft((d) => ({ ...d, [id]: { ...d[id], ...patch } }))
  }

  const save = () => {
    if (hasErrors) return
    const payload: ExamSubjectConfigInput[] = subjects
      .filter((s) => draft[s.id].included)
      .map((s) => ({ subject_id: s.id, max_marks: Number(draft[s.id].max), pass_marks: Number(draft[s.id].pass) }))
    replace.mutate(payload, {
      onSuccess: () => {
        setSaved(true)
        onDone?.()
      },
    })
  }

  return (
    <div className="space-y-4">
      <table className="min-w-full text-sm">
        <caption className="sr-only">Subject configuration</caption>
        <thead>
          <tr className="text-left text-xs tracking-wide text-slate-500 uppercase">
            <th scope="col" className="py-2">
              Subject
            </th>
            <th scope="col" className="py-2">
              Max marks
            </th>
            <th scope="col" className="py-2">
              Pass marks
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {subjects.map((s, i) => {
            const row = draft[s.id]
            return (
              <tr key={s.id}>
                <td className="py-2 pr-3">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={row.included}
                      onChange={(e) => update(s.id, { included: e.target.checked })}
                      className="size-4 accent-brand-600"
                    />
                    <span className="font-medium text-slate-800 dark:text-slate-100">{s.name}</span>
                  </label>
                  {errors[i] && <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">{errors[i]}</p>}
                </td>
                <td className="py-2 pr-3">
                  <input
                    type="number"
                    min={1}
                    aria-label={`${s.name} max marks`}
                    disabled={!row.included}
                    value={row.max}
                    onChange={(e) => update(s.id, { max: e.target.value })}
                    className={inputClass(errors[i] !== null)}
                  />
                </td>
                <td className="py-2">
                  <input
                    type="number"
                    min={0}
                    aria-label={`${s.name} pass marks`}
                    disabled={!row.included}
                    value={row.pass}
                    onChange={(e) => update(s.id, { pass: e.target.value })}
                    className={inputClass(errors[i] !== null)}
                  />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <ErrorAlert error={replace.error} />
      {saved && <p className="text-sm text-emerald-600">Saved.</p>}
      <div className="flex justify-end">
        <GradientButton icon={Save} onClick={save} disabled={hasErrors} loading={replace.isPending}>
          Save subjects
        </GradientButton>
      </div>
    </div>
  )
}

function inputClass(invalid: boolean): string {
  return cn(
    'h-9 w-28 rounded-lg border bg-white px-2 text-sm outline-none focus:ring-2 focus:ring-brand-500/30 disabled:opacity-50',
    'dark:bg-slate-900 dark:text-slate-100',
    invalid ? 'border-rose-400' : 'border-slate-200 dark:border-slate-700',
  )
}
