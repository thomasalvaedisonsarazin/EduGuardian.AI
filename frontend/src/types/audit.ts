/** Types for /api/v1/audit-logs (mirror backend/app/schemas/audit.py). */
import type { ID, ISODateTime, JsonObject } from '@/types'

export interface AuditEntry {
  id: ID
  user_id: ID | null
  user_email: string | null
  /** "user" or an agent name such as "InterventionAgent". */
  actor: string
  action: string
  entity_type: string
  entity_id: ID | null
  detail: JsonObject | null
  created_at: ISODateTime
}

export interface AuditList {
  items: AuditEntry[]
  total: number
  actors: string[]
  entity_types: string[]
}

export interface AuditFilters {
  actor?: string
  entity_type?: string
  limit?: number
  offset?: number
}
