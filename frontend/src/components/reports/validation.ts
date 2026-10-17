import type { ID, Role } from '@/types'
import type { ReportCreateInput, ReportFormat, ReportKind } from '@/types/reports'

/** Raw form state: selects hold strings ('' = nothing chosen). */
export interface ReportFormValues {
  kind: ReportKind
  format: ReportFormat
  examId: string
  classSectionId: string
  teacherId: string
}

export type ReportFormErrors = Partial<Record<'kind' | 'examId' | 'classSectionId' | 'teacherId', string>>

export const INITIAL_REPORT_FORM: ReportFormValues = {
  kind: 'principal',
  format: 'pdf',
  examId: '',
  classSectionId: '',
  teacherId: '',
}

function toId(raw: string): ID | null {
  if (!/^\d+$/.test(raw)) return null
  const n = Number(raw)
  return n > 0 ? n : null
}

/** Report kinds a role may generate (teachers cannot generate the principal report). */
export function allowedKinds(role: Role | null): ReportKind[] {
  return role === 'teacher' ? ['class_teacher', 'subject_teacher'] : ['principal', 'class_teacher', 'subject_teacher']
}

export function validateReportForm(values: ReportFormValues, role: Role | null = null): ReportFormErrors {
  const errors: ReportFormErrors = {}
  if (!allowedKinds(role).includes(values.kind)) errors.kind = 'You cannot generate this report type.'
  if (toId(values.examId) === null) errors.examId = 'Choose an exam.'
  if (values.kind === 'class_teacher' && toId(values.classSectionId) === null) errors.classSectionId = 'Choose a class.'
  if (values.kind === 'subject_teacher' && toId(values.teacherId) === null) errors.teacherId = 'Choose a teacher.'
  return errors
}

/** Builds the POST /reports body; only includes the scope field the kind needs. Null when invalid. */
export function toReportInput(values: ReportFormValues, role: Role | null = null): ReportCreateInput | null {
  if (Object.keys(validateReportForm(values, role)).length > 0) return null
  const examId = toId(values.examId)
  if (examId === null) return null
  const input: ReportCreateInput = { kind: values.kind, format: values.format, exam_id: examId }
  if (values.kind === 'class_teacher') input.class_section_id = toId(values.classSectionId) ?? undefined
  if (values.kind === 'subject_teacher') input.teacher_id = toId(values.teacherId) ?? undefined
  return input
}
