import { Play } from 'lucide-react'
import { useId, useState } from 'react'
import { GlassCard, GradientButton } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { ID } from '@/types'
import type { ExamListItem } from '@/types/analytics'

export interface ClassOption {
  id: ID
  label: string
}

export interface RunAnalysisCardProps {
  exams: readonly ExamListItem[]
  classes: readonly ClassOption[]
  loading?: boolean
  starting?: boolean
  error?: string | null
  onStart: (examId: ID, classSectionIds: ID[]) => void
}

/** Pick an exam (and optionally classes) and start the multi-agent analysis. */
export function RunAnalysisCard({ exams, classes, loading = false, starting = false, error, onStart }: RunAnalysisCardProps) {
  const selectId = useId()
  const withMarks = exams.filter((e) => e.has_marks)
  const [examId, setExamId] = useState<ID | null>(null)
  const [selected, setSelected] = useState<ID[]>([])
  const effectiveExam = examId ?? withMarks[withMarks.length - 1]?.exam.id ?? null

  const toggle = (id: ID) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  return (
    <GlassCard hoverable={false} className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Run analysis</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Data quality, performance analysis, intervention drafting and reports in one run. Plans stay drafts until a
          teacher or coordinator approves them.
        </p>
      </div>

      <div className="space-y-1.5">
        <label htmlFor={selectId} className="block text-sm font-medium text-slate-700 dark:text-slate-200">
          Exam
        </label>
        <select
          id={selectId}
          value={effectiveExam ?? ''}
          disabled={loading || withMarks.length === 0}
          onChange={(e) => setExamId(e.target.value ? Number(e.target.value) : null)}
          className="h-11 w-full rounded-xl border border-slate-200 bg-white/80 px-3 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-100"
        >
          {withMarks.length === 0 && <option value="">{loading ? 'Loading exams…' : 'No exams with marks yet'}</option>}
          {withMarks.map((e) => (
            <option key={e.exam.id} value={e.exam.id}>
              {e.exam.name} ({e.exam.academic_year_label}) · {e.mark_count} marks
            </option>
          ))}
        </select>
      </div>

      {classes.length > 0 && (
        <fieldset className="space-y-1.5">
          <legend className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Classes <span className="font-normal text-slate-400">(optional — all classes when none selected)</span>
          </legend>
          <div className="flex flex-wrap gap-2">
            {classes.map((c) => {
              const on = selected.includes(c.id)
              return (
                <button
                  key={c.id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(c.id)}
                  className={cn(
                    'cursor-pointer rounded-full border px-3 py-1 text-sm transition-colors',
                    on
                      ? 'border-brand-500 bg-brand-600 text-white'
                      : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200',
                  )}
                >
                  {c.label}
                </button>
              )
            })}
          </div>
        </fieldset>
      )}

      {error && (
        <p role="alert" className="text-sm text-rose-600 dark:text-rose-400">
          {error}
        </p>
      )}

      <GradientButton
        icon={Play}
        loading={starting}
        disabled={effectiveExam === null}
        onClick={() => effectiveExam !== null && onStart(effectiveExam, selected)}
      >
        Start agents
      </GradientButton>
    </GlassCard>
  )
}
