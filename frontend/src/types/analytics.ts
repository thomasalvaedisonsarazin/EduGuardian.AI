/**
 * Types for /api/v1/analytics (mirror backend/app/schemas/analytics.py).
 * Decimal fields arrive as strings such as "72.50" - convert with `toNum()` before charting.
 */
import type { ID, ISODate, JsonObject } from '@/types'

export type DecimalString = string

export interface ExamRef {
  id: ID
  name: string
  sequence: number
  held_on: ISODate | null
  academic_year_id: ID
  academic_year_label: string
}

export interface ExamListItem {
  exam: ExamRef
  mark_count: number
  has_marks: boolean
}

export interface SubjectConfig {
  subject_id: ID
  name: string
  max_marks: DecimalString
  pass_marks: DecimalString
}

export interface StudentInfo {
  student_id: ID
  pseudo_id: string
  full_name: string
  class_section_id: ID
  class_label: string
}

export interface SubjectResult {
  subject_id: ID
  subject_name: string
  marks: DecimalString | null
  max_marks: DecimalString
  pass_marks: DecimalString
  is_absent: boolean
  is_missing: boolean
  passed: boolean
  percentage: DecimalString
}

export interface StudentResult extends StudentInfo {
  subjects: SubjectResult[]
  total: DecimalString
  max_total: DecimalString
  percentage: DecimalString
  passed: boolean
  appeared: boolean
  failed_subjects: ID[]
  rank_in_section: number
  section_size: number
}

export interface DistributionBand {
  label: string
  lower: DecimalString
  upper: DecimalString
  count: number
}

export interface ClassSummary {
  class_section_id: ID | null
  class_label: string
  student_count: number
  appeared_count: number
  pass_count: number
  fail_count: number
  pass_percentage: DecimalString | null
  mean_percentage: DecimalString | null
  median_percentage: DecimalString | null
  highest_percentage: DecimalString | null
  lowest_percentage: DecimalString | null
  distribution: DistributionBand[]
}

export interface SubjectStats {
  student_count: number
  appeared_count: number
  absent_count: number
  missing_count: number
  pass_count: number
  pass_percentage: DecimalString | null
  mean_marks: DecimalString | null
  mean_percentage: DecimalString | null
  highest_marks: DecimalString | null
  lowest_marks: DecimalString | null
}

export interface SectionSubjectStats {
  class_section_id: ID
  class_label: string
  stats: SubjectStats
}

export interface SubjectSummary {
  subject_id: ID
  subject_name: string
  max_marks: DecimalString
  pass_marks: DecimalString
  overall: SubjectStats
  sections: SectionSubjectStats[]
  weakest_sections: ID[]
  mean_percentage_change: DecimalString | null
}

export interface SubjectChange {
  subject_id: ID
  subject_name: string
  previous_percentage: DecimalString
  current_percentage: DecimalString
  delta: DecimalString
}

export interface StudentChange {
  student_id: ID
  previous_percentage: DecimalString
  current_percentage: DecimalString
  delta: DecimalString
  subjects: SubjectChange[]
}

export type RiskCode = 'FAILED_SUBJECTS' | 'SHARP_DROP' | 'LOW_OVERALL'
export type RiskSeverity = 'high' | 'medium'

export interface RiskReason {
  code: RiskCode
  detail: string
  evidence: JsonObject
}

export interface AtRiskStudent extends StudentInfo {
  percentage: DecimalString
  failed_subject_count: number
  delta: DecimalString | null
  severity: RiskSeverity
  reasons: RiskReason[]
}

export interface ExamSummary {
  exam: ExamRef
  previous_exam: ExamRef | null
  comparison_exam_id: ID | null
  class_section_ids: ID[] | null
  subjects: SubjectConfig[]
  school_summary: ClassSummary
  class_summaries: ClassSummary[]
  subject_summaries: SubjectSummary[]
  at_risk_count: number
  at_risk_high_count: number
  at_risk: AtRiskStudent[]
}

export interface ClassAnalytics {
  exam: ExamRef
  previous_exam: ExamRef | null
  class_section_id: ID
  class_label: string
  summary: ClassSummary
  subjects: SubjectConfig[]
  subject_summaries: SubjectSummary[]
  results: StudentResult[]
  changes: StudentChange[]
  at_risk: AtRiskStudent[]
}

export interface SubjectStudentRow {
  student_id: ID
  pseudo_id: string
  full_name: string
  class_section_id: ID
  class_label: string
  marks: DecimalString | null
  is_absent: boolean
  is_missing: boolean
  passed: boolean
  percentage: DecimalString
  delta: DecimalString | null
}

export interface SubjectAnalytics {
  exam: ExamRef
  previous_exam: ExamRef | null
  summary: SubjectSummary
  students: SubjectStudentRow[]
}

export interface AtRiskList {
  exam: ExamRef
  previous_exam: ExamRef | null
  count: number
  high_count: number
  students: AtRiskStudent[]
}

export interface StudentTrendPoint {
  exam: ExamRef
  result: StudentResult
  comparison_exam_id: ID | null
  change: StudentChange | null
  at_risk: AtRiskStudent | null
  section_pass_percentage: DecimalString | null
  section_mean_percentage: DecimalString | null
}

export interface StudentTrend {
  student: StudentInfo
  points: StudentTrendPoint[]
}

export interface ExamTrendPoint {
  exam: ExamRef
  student_count: number
  pass_percentage: DecimalString | null
  mean_percentage: DecimalString | null
  median_percentage: DecimalString | null
}

export interface DashboardOverview {
  student_count: number
  class_section_count: number
  exams_with_marks: number
  latest_exam: ExamRef | null
  previous_exam: ExamRef | null
  summary: ClassSummary | null
  at_risk_count: number
  at_risk_high_count: number
  at_risk_preview: AtRiskStudent[]
  subjects: SubjectSummary[]
  trend: ExamTrendPoint[]
}
