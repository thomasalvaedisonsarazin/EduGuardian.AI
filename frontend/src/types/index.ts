/**
 * Shared domain types mirroring the backend models (see INITIAL.md / backend/app/models).
 * IDs are integers. Datetimes/dates are ISO-8601 strings.
 * Numeric(…) columns may be serialised by Pydantic as either a JSON number or a string.
 */

export type ID = number
export type ISODateTime = string
export type ISODate = string
export type DecimalValue = number | string

/** Arbitrary JSON payloads (JSON/JSONB columns). */
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }
export type JsonObject = { [key: string]: JsonValue }

// ---------------------------------------------------------------------------
// Module 1: Auth & Tenancy
// ---------------------------------------------------------------------------

export type Role = 'school_admin' | 'principal' | 'coordinator' | 'teacher'

export const ROLES: readonly Role[] = ['school_admin', 'principal', 'coordinator', 'teacher']

export interface School {
  id: ID
  name: string
  code: string
  created_at: ISODateTime
}

export interface Membership {
  id: ID
  user_id: ID
  school_id: ID
  role: Role
  /** Populated by GET /auth/me for the school switcher. */
  school?: School
}

export interface User {
  id: ID
  email: string
  full_name: string
  is_active: boolean
  is_superadmin: boolean
  created_at: ISODateTime
}

/** GET /auth/me response. */
export interface MeResponse extends User {
  memberships: Membership[]
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
  school_name: string
  school_code: string
}

// ---------------------------------------------------------------------------
// Generic API shapes
// ---------------------------------------------------------------------------

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details?: JsonValue
  }
}

// ---------------------------------------------------------------------------
// Module 2: Academic Setup
// ---------------------------------------------------------------------------

export interface AcademicYear {
  id: ID
  school_id: ID
  label: string
  is_current: boolean
}

export interface ClassSection {
  id: ID
  school_id: ID
  academic_year_id: ID
  grade: number
  section: string
}

export interface Subject {
  id: ID
  school_id: ID
  name: string
  code: string
}

export interface Teacher {
  id: ID
  school_id: ID
  user_id: ID | null
  full_name: string
}

export interface TeachingAssignment {
  id: ID
  school_id: ID
  teacher_id: ID
  class_section_id: ID
  subject_id: ID
  is_class_teacher: boolean
}

export interface Student {
  id: ID
  school_id: ID
  class_section_id: ID
  admission_no: string
  full_name: string
  pseudo_id: string
}

export interface Exam {
  id: ID
  school_id: ID
  academic_year_id: ID
  name: string
  sequence: number
  held_on: ISODate | null
}

export interface ExamSubjectConfig {
  id: ID
  school_id: ID
  exam_id: ID
  subject_id: ID
  max_marks: DecimalValue
  pass_marks: DecimalValue
}

// ---------------------------------------------------------------------------
// Module 3: Marks Import
// ---------------------------------------------------------------------------

export interface Mark {
  id: ID
  school_id: ID
  exam_id: ID
  student_id: ID
  subject_id: ID
  marks_obtained: DecimalValue | null
  is_absent: boolean
}

export type ImportStatus = 'uploaded' | 'validated' | 'committed' | 'rejected'

export interface ImportIssue {
  code: string
  message: string
  severity?: 'error' | 'warning'
  row?: number | null
  column?: string | null
}

export interface ImportBatch {
  id: ID
  school_id: ID
  exam_id: ID
  filename: string
  status: ImportStatus
  column_map: JsonObject | null
  issues: ImportIssue[] | null
  uploaded_by: ID | null
  created_at: ISODateTime
}

// ---------------------------------------------------------------------------
// Module 5: Agents & Interventions
// ---------------------------------------------------------------------------

export type AgentRunKind = 'full_analysis' | 'intervention_draft' | 'report'
export type AgentRunStatus = 'queued' | 'running' | 'awaiting_approval' | 'done' | 'failed'
export type AgentStepStatus = 'pending' | 'running' | 'done' | 'failed' | 'skipped'

export interface AgentStep {
  id: ID
  run_id: ID
  agent_name: string
  status: AgentStepStatus
  started_at: ISODateTime | null
  finished_at: ISODateTime | null
  input_summary: JsonObject | null
  output_summary: JsonObject | null
  error: string | null
}

export interface AgentRun {
  id: ID
  school_id: ID
  kind: AgentRunKind
  status: AgentRunStatus
  requested_by: ID | null
  input: JsonObject | null
  created_at: ISODateTime
  finished_at: ISODateTime | null
  token_usage: number
  cost_usd: DecimalValue
  error: string | null
  steps?: AgentStep[]
}

export type InterventionStatus = 'draft' | 'approved' | 'rejected' | 'in_progress' | 'completed'

export interface InterventionPlan {
  id: ID
  school_id: ID
  run_id: ID | null
  student_id: ID
  subject_id: ID | null
  status: InterventionStatus
  evidence: JsonObject | null
  plan_text: string
  activities: JsonValue[] | null
  reassess_on: ISODate | null
  approved_by: ID | null
  approved_at: ISODateTime | null
}

export interface AuditLog {
  id: ID
  school_id: ID
  user_id: ID | null
  /** "user" or the agent name, e.g. "data_quality". */
  actor: string
  action: string
  entity_type: string
  entity_id: ID | null
  detail: JsonObject | null
  created_at: ISODateTime
}

// ---------------------------------------------------------------------------
// Module 6: Reports
// ---------------------------------------------------------------------------

export type ReportKind = 'principal' | 'class_teacher' | 'subject_teacher'
export type ReportFormat = 'pdf' | 'xlsx'

export interface Report {
  id: ID
  school_id: ID
  run_id: ID | null
  kind: ReportKind
  format: ReportFormat
  file_path: string
  created_by: ID | null
  created_at: ISODateTime
}
