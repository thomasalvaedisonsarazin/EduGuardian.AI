import { FileSpreadsheet, FileText, Sparkles } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { GradientButton } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { ClassSection, Role, Teacher } from '@/types'
import type { ExamListItem } from '@/types/analytics'
import {
  REPORT_KIND_DESCRIPTIONS,
  REPORT_KIND_LABELS,
  type ReportCreateInput,
  type ReportFormat,
  type ReportKind,
} from '@/types/reports'
import {
  INITIAL_REPORT_FORM,
  allowedKinds,
  toReportInput,
  validateReportForm,
  type ReportFormErrors,
  type ReportFormValues,
} from './validation'

export interface GenerateReportFormProps {
  exams: readonly ExamListItem[]
  classes: readonly ClassSection[]
  teachers: readonly Teacher[]
  /** The caller's role in the active school (teachers cannot generate principal reports). */
  userRole: Role | null
  submitting?: boolean
  onSubmit: (input: ReportCreateInput) => void
}

const selectClass = cn(
  'h-10 w-full rounded-xl border border-slate-200 bg-white/80 px-3 text-sm text-slate-900 outline-none',
  'focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15',
  'dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-100',
)
const labelClass = 'mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200'
const errorClass = 'mt-1 text-xs text-rose-600 dark:text-rose-400'

const FORMATS: { value: ReportFormat; label: string; icon: typeof FileText }[] = [
  { value: 'pdf', label: 'PDF', icon: FileText },
  { value: 'xlsx', label: 'Excel', icon: FileSpreadsheet },
]

function classLabel(c: ClassSection): string {
  return `${c.grade}-${c.section}`
}

export function GenerateReportForm({ exams, classes, teachers, userRole, submitting = false, onSubmit }: GenerateReportFormProps) {
  const kinds = allowedKinds(userRole)
  const latestWithMarks = [...exams].reverse().find((e) => e.has_marks)
  const [values, setValues] = useState<ReportFormValues>(() => ({
    ...INITIAL_REPORT_FORM,
    kind: kinds[0] ?? 'principal',
    examId: latestWithMarks ? String(latestWithMarks.exam.id) : '',
  }))
  const [errors, setErrors] = useState<ReportFormErrors>({})
  const [touched, setTouched] = useState(false)
  const ids = { kind: useId(), exam: useId(), cls: useId(), teacher: useId(), format: useId() }

  const update = (patch: Partial<ReportFormValues>) => {
    const next = { ...values, ...patch }
    setValues(next)
    if (touched) setErrors(validateReportForm(next, userRole))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setTouched(true)
    const found = validateReportForm(values, userRole)
    setErrors(found)
    const input = toReportInput(values, userRole)
    if (input) onSubmit(input)
  }

  const sortedClasses = [...classes].sort((a, b) => a.grade - b.grade || a.section.localeCompare(b.section))
  const sortedTeachers = [...teachers].sort((a, b) => a.full_name.localeCompare(b.full_name))

  return (
    <form noValidate onSubmit={handleSubmit} aria-label="Generate report" className="flex flex-col gap-4">
      <div>
        <label htmlFor={ids.kind} className={labelClass}>
          Report type
        </label>
        <select
          id={ids.kind}
          value={values.kind}
          onChange={(e) => update({ kind: e.target.value as ReportKind })}
          className={selectClass}
        >
          {kinds.map((k) => (
            <option key={k} value={k}>
              {REPORT_KIND_LABELS[k]}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{REPORT_KIND_DESCRIPTIONS[values.kind]}</p>
        {errors.kind && <p className={errorClass}>{errors.kind}</p>}
      </div>

      <div>
        <label htmlFor={ids.exam} className={labelClass}>
          Exam
        </label>
        <select
          id={ids.exam}
          value={values.examId}
          onChange={(e) => update({ examId: e.target.value })}
          aria-invalid={Boolean(errors.examId) || undefined}
          className={selectClass}
        >
          <option value="">Select an exam</option>
          {exams.map((item) => (
            <option key={item.exam.id} value={item.exam.id}>
              {item.exam.name} ({item.exam.academic_year_label}){item.has_marks ? '' : ' - no marks yet'}
            </option>
          ))}
        </select>
        {errors.examId && <p className={errorClass}>{errors.examId}</p>}
      </div>

      {values.kind === 'class_teacher' && (
        <div>
          <label htmlFor={ids.cls} className={labelClass}>
            Class
          </label>
          <select
            id={ids.cls}
            value={values.classSectionId}
            onChange={(e) => update({ classSectionId: e.target.value })}
            aria-invalid={Boolean(errors.classSectionId) || undefined}
            className={selectClass}
          >
            <option value="">Select a class</option>
            {sortedClasses.map((c) => (
              <option key={c.id} value={c.id}>
                {classLabel(c)}
              </option>
            ))}
          </select>
          {errors.classSectionId && <p className={errorClass}>{errors.classSectionId}</p>}
        </div>
      )}

      {values.kind === 'subject_teacher' && (
        <div>
          <label htmlFor={ids.teacher} className={labelClass}>
            Teacher
          </label>
          <select
            id={ids.teacher}
            value={values.teacherId}
            onChange={(e) => update({ teacherId: e.target.value })}
            aria-invalid={Boolean(errors.teacherId) || undefined}
            className={selectClass}
          >
            <option value="">Select a teacher</option>
            {sortedTeachers.map((t) => (
              <option key={t.id} value={t.id}>
                {t.full_name}
              </option>
            ))}
          </select>
          {errors.teacherId && <p className={errorClass}>{errors.teacherId}</p>}
        </div>
      )}

      <fieldset>
        <legend className={labelClass}>Format</legend>
        <div className="inline-flex rounded-full bg-slate-100 p-1 dark:bg-slate-800">
          {FORMATS.map(({ value, label, icon: Icon }) => {
            const active = values.format === value
            return (
              <label
                key={value}
                className={cn(
                  'inline-flex cursor-pointer items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-medium transition-colors',
                  'has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-500',
                  active
                    ? 'bg-white text-brand-700 shadow-sm dark:bg-slate-950 dark:text-brand-300'
                    : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white',
                )}
              >
                <input
                  type="radio"
                  name={ids.format}
                  value={value}
                  checked={active}
                  onChange={() => update({ format: value })}
                  className="sr-only"
                />
                <Icon aria-hidden className="size-4" />
                {label}
              </label>
            )
          })}
        </div>
      </fieldset>

      <GradientButton type="submit" icon={Sparkles} loading={submitting} fullWidth>
        {submitting ? 'Generating...' : 'Generate report'}
      </GradientButton>
    </form>
  )
}
