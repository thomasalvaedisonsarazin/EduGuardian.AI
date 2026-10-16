import type { BadgeTone } from '@/components/ui'
import type { ImportStatus } from '@/types'
import type { IssueSeverity, ValidationIssue } from '@/types/imports'

export const ISSUE_LABELS: Record<string, string> = {
  UNKNOWN_STUDENT: 'Unknown student',
  DUPLICATE_STUDENT_ROW: 'Duplicate row',
  MARK_ABOVE_MAX: 'Above max marks',
  NEGATIVE_MARK: 'Negative mark',
  NON_NUMERIC: 'Not a number',
  NO_ADMISSION_COLUMN: 'No admission column',
  MISSING_MARK: 'Blank mark',
  ABSENT: 'Absent',
  UNMAPPED_COLUMN: 'Unmapped column',
  MISSING_SUBJECT_COLUMN: 'Missing subject column',
  STUDENT_NOT_IN_FILE: 'Student missing from file',
}

/** Codes the backend reports with severity "error". */
export const ERROR_CODES: ReadonlySet<string> = new Set([
  'UNKNOWN_STUDENT',
  'DUPLICATE_STUDENT_ROW',
  'MARK_ABOVE_MAX',
  'NEGATIVE_MARK',
  'NON_NUMERIC',
  'NO_ADMISSION_COLUMN',
])

export function issueLabel(code: string): string {
  return ISSUE_LABELS[code] ?? code
}

export const SEVERITY_TONE: Record<IssueSeverity, BadgeTone> = { error: 'danger', warning: 'warning' }

export const STATUS_TONE: Record<ImportStatus, BadgeTone> = {
  uploaded: 'neutral',
  validated: 'info',
  committed: 'success',
  rejected: 'danger',
}

/** "row|column" -> worst severity, for highlighting preview cells. */
export function cellIssueIndex(issues: readonly ValidationIssue[]): Map<string, IssueSeverity> {
  const index = new Map<string, IssueSeverity>()
  for (const issue of issues) {
    if (issue.row === null || issue.column === null) continue
    const key = `${issue.row}|${issue.column}`
    if (index.get(key) !== 'error') index.set(key, issue.severity)
  }
  return index
}

export function formatDateTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}
