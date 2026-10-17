/** Types for /api/v1/agent-runs (mirror backend/app/schemas/agent_runs.py). */
import type { AgentRunKind, AgentRunStatus, AgentStepStatus, ID, ISODateTime, JsonObject } from '@/types'

export type LlmMode = 'llm' | 'template' | 'mixed' | 'none'

export interface AgentStepDetail {
  id: ID
  run_id: ID
  agent_name: string
  status: AgentStepStatus
  started_at: ISODateTime | null
  finished_at: ISODateTime | null
  duration_ms: number | null
  input_summary: JsonObject | null
  output_summary: JsonObject | null
  error: string | null
}

export interface RunReport {
  id: ID
  kind: string
  format: string
  created_at: ISODateTime
}

export interface AgentRunSummary {
  id: ID
  school_id: ID
  kind: AgentRunKind
  status: AgentRunStatus
  requested_by: ID | null
  requested_by_email: string | null
  input: JsonObject | null
  exam_id: ID | null
  exam_name: string | null
  created_at: ISODateTime
  finished_at: ISODateTime | null
  token_usage: number
  /** Decimal serialised as a string, e.g. "0.0123". */
  cost_usd: string | number
  error: string | null
  llm_mode: LlmMode | string | null
  plan_counts: Partial<Record<string, number>>
}

export interface AgentRunDetail extends AgentRunSummary {
  steps: AgentStepDetail[]
  reports: RunReport[]
  warnings: string[]
}

export interface AgentRunList {
  items: AgentRunSummary[]
  total: number
}

export interface StartRunInput {
  exam_id: ID
  class_section_ids?: ID[] | null
}
