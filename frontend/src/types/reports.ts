/** Module 6 - Reports (mirrors backend/app/schemas/reports.py). */
import type { ID, ISODateTime, ReportFormat, ReportKind } from '@/types'

export type { ReportFormat, ReportKind }

export interface ReportItem {
  id: ID
  school_id: ID
  run_id: ID | null
  kind: ReportKind
  format: ReportFormat
  exam_id: ID | null
  exam_name: string | null
  class_section_id: ID | null
  teacher_id: ID | null
  scope_label: string
  file_name: string
  size_bytes: number | null
  created_by: ID | null
  created_by_name: string | null
  created_at: ISODateTime
  download_url: string
}

export interface ReportCreateInput {
  kind: ReportKind
  format: ReportFormat
  exam_id: ID
  class_section_id?: ID
  teacher_id?: ID
}

export interface ReportListFilters {
  exam_id?: ID
  kind?: ReportKind
  run_id?: ID
}

export const REPORT_KIND_LABELS: Record<ReportKind, string> = {
  principal: 'Principal',
  class_teacher: 'Class teacher',
  subject_teacher: 'Subject teacher',
}

export const REPORT_KIND_DESCRIPTIONS: Record<ReportKind, string> = {
  principal: 'Whole-school figures, classes, subjects, at-risk summary and plan status.',
  class_teacher: 'One class: every student result, at-risk students and their plans.',
  subject_teacher: "A teacher's classes and the students who need support (coaching view).",
}
