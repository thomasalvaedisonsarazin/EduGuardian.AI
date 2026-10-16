/** Types for /api/v1/imports (Module 3: marks import + Data Quality Agent). */
import type { DecimalValue, ID, ImportStatus, ISODateTime } from '@/types'

export type IssueSeverity = 'error' | 'warning'

export type IssueCode =
  | 'UNKNOWN_STUDENT'
  | 'DUPLICATE_STUDENT_ROW'
  | 'MARK_ABOVE_MAX'
  | 'NEGATIVE_MARK'
  | 'NON_NUMERIC'
  | 'NO_ADMISSION_COLUMN'
  | 'MISSING_MARK'
  | 'ABSENT'
  | 'UNMAPPED_COLUMN'
  | 'MISSING_SUBJECT_COLUMN'
  | 'STUDENT_NOT_IN_FILE'

export interface ValidationIssue {
  /** 1-based data row (header excluded); null for file/column-level issues. */
  row: number | null
  column: string | null
  code: IssueCode | string
  severity: IssueSeverity
  message: string
}

export interface IssueSummary {
  errors: number
  warnings: number
  by_code: Record<string, number>
}

export interface ColumnMap {
  admission_column: string | null
  /** header -> subject id (null = ignored). */
  subjects: Record<string, ID | null>
}

export interface PreviewCell {
  subject_id: ID
  raw: string
  value: string | null
  is_absent: boolean
}

export interface PreviewRow {
  row: number
  admission_no: string
  student_id: ID | null
  /** keyed by file header */
  marks: Record<string, PreviewCell>
}

export interface ExamSubject {
  id: ID
  name: string
  code: string
  max_marks: DecimalValue
  pass_marks: DecimalValue
}

export interface ImportBatchListItem {
  id: ID
  exam_id: ID
  exam_name: string | null
  filename: string
  status: ImportStatus
  row_count: number
  summary: IssueSummary
  created_at: ISODateTime
}

export interface ImportBatchDetail extends ImportBatchListItem {
  column_map: ColumnMap
  headers: string[]
  issues: ValidationIssue[]
  summary_text: string
  /** First 50 normalized rows. */
  preview: PreviewRow[]
  can_commit: boolean
  exam_subjects: ExamSubject[]
  uploaded_by: ID | null
}

export interface CommitResult {
  batch_id: ID
  inserted: number
  updated: number
  absent: number
  skipped: number
}

export interface UploadImportInput {
  examId: ID
  file: File
}
