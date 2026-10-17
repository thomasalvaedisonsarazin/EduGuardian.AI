/** Typed readers for the evidence JSON stored on an intervention plan (written by the backend
 * Intervention Agent: AtRiskStudent.to_dict() + exam info + per-subject results + draft meta). */
import type { BadgeTone } from '@/components/ui'
import type { InterventionStatus, JsonObject, JsonValue } from '@/types'
import type { RiskCode, RiskReason } from '@/types/analytics'

const RISK_CODES: readonly RiskCode[] = ['FAILED_SUBJECTS', 'SHARP_DROP', 'LOW_OVERALL']

function isObject(value: JsonValue | undefined): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function str(value: JsonValue | undefined): string | null {
  if (value === null || value === undefined) return null
  return typeof value === 'string' ? value : String(value)
}

export function parseReasons(evidence: JsonObject | null): RiskReason[] {
  const raw = evidence?.reasons
  if (!Array.isArray(raw)) return []
  const out: RiskReason[] = []
  for (const item of raw) {
    if (!isObject(item)) continue
    const code = item.code
    if (typeof code !== 'string' || !RISK_CODES.includes(code as RiskCode)) continue
    out.push({
      code: code as RiskCode,
      detail: str(item.detail) ?? '',
      evidence: isObject(item.evidence) ? item.evidence : {},
    })
  }
  return out
}

export interface FailedSubject {
  name: string
  marks: string | null
  maxMarks: string | null
  passMarks: string | null
  absent: boolean
}

export function failedSubjects(evidence: JsonObject | null): FailedSubject[] {
  const reason = parseReasons(evidence).find((r) => r.code === 'FAILED_SUBJECTS')
  const subjects = reason?.evidence.subjects
  if (!Array.isArray(subjects)) return []
  return subjects.filter(isObject).map((s) => ({
    name: str(s.subject_name) ?? 'Subject',
    marks: str(s.marks),
    maxMarks: str(s.max_marks),
    passMarks: str(s.pass_marks),
    absent: s.is_absent === true,
  }))
}

export interface DropInfo {
  previous: string | null
  current: string | null
  delta: string | null
}

export function dropInfo(evidence: JsonObject | null): DropInfo | null {
  const reason = parseReasons(evidence).find((r) => r.code === 'SHARP_DROP')
  if (!reason) return null
  return {
    previous: str(reason.evidence.previous_percentage),
    current: str(reason.evidence.current_percentage),
    delta: str(reason.evidence.delta),
  }
}

export interface DraftMeta {
  mode: string | null
  summary: string | null
  focusAreas: string[]
  rationale: string | null
}

export function draftMeta(evidence: JsonObject | null): DraftMeta {
  const draft = evidence?.draft
  if (!isObject(draft)) return { mode: null, summary: null, focusAreas: [], rationale: null }
  const focus = Array.isArray(draft.focus_areas) ? draft.focus_areas.map((f) => String(f)) : []
  return { mode: str(draft.mode), summary: str(draft.summary), focusAreas: focus, rationale: str(draft.rationale) }
}

export function rejectionReason(evidence: JsonObject | null): string | null {
  const rejection = evidence?.rejection
  return isObject(rejection) ? str(rejection.reason) : null
}

export function overallPercentage(evidence: JsonObject | null): string | null {
  return str(evidence?.percentage)
}

export const STATUS_LABELS: Record<InterventionStatus, string> = {
  draft: 'Draft',
  approved: 'Approved',
  in_progress: 'In progress',
  completed: 'Completed',
  rejected: 'Rejected',
}

export const STATUS_TONES: Record<InterventionStatus, BadgeTone> = {
  draft: 'warning',
  approved: 'success',
  in_progress: 'info',
  completed: 'brand',
  rejected: 'neutral',
}

export const STATUS_ORDER: readonly InterventionStatus[] = ['draft', 'approved', 'in_progress', 'completed', 'rejected']
