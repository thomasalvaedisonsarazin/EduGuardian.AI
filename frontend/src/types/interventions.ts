/** Types for /api/v1/interventions (mirror backend/app/schemas/interventions.py). */
import type { ID, ISODate, ISODateTime, InterventionStatus, JsonObject } from '@/types'

export type ActivityOwner = 'teacher' | 'student' | 'parent'

export interface PlanActivity {
  title: string
  description: string
  frequency: string
  owner: ActivityOwner
}

export interface InterventionStudent {
  id: ID
  full_name: string
  pseudo_id: string
  admission_no: string
  class_section_id: ID
  class_label: string
}

export interface InterventionItem {
  id: ID
  run_id: ID | null
  student: InterventionStudent
  subject_id: ID | null
  subject_name: string | null
  status: InterventionStatus
  severity: 'high' | 'medium' | string | null
  exam_id: ID | null
  exam_name: string | null
  evidence: JsonObject | null
  plan_text: string
  activities: PlanActivity[]
  reassess_on: ISODate | null
  approved_by: ID | null
  approved_by_email: string | null
  approved_at: ISODateTime | null
  created_at: ISODateTime
  updated_at: ISODateTime | null
  can_review: boolean
}

export interface InterventionList {
  items: InterventionItem[]
  total: number
  counts: Partial<Record<InterventionStatus, number>>
}

export interface InterventionFilters {
  status?: InterventionStatus
  class_section_id?: ID
  exam_id?: ID
  run_id?: ID
}

export interface InterventionUpdateInput {
  plan_text?: string
  activities?: PlanActivity[]
  reassess_on?: ISODate | null
}
