import { Bot, ClipboardCheck, FileText, LineChart, ShieldCheck, type LucideIcon } from 'lucide-react'
import type { BadgeTone } from '@/components/ui'
import type { AgentRunStatus, AgentStepStatus, JsonObject, JsonValue } from '@/types'

export interface AgentMeta {
  label: string
  description: string
  icon: LucideIcon
}

/** Pipeline order (matches backend app/agents/state.py AGENT_ORDER). */
export const AGENT_ORDER = [
  'DataQualityAgent',
  'PerformanceAnalysisAgent',
  'InterventionAgent',
  'ReportingAgent',
  'Orchestrator',
] as const

export const AGENT_META: Record<string, AgentMeta> = {
  DataQualityAgent: {
    label: 'Data Quality',
    description: 'Checks committed marks for gaps, absences and unconfigured subjects.',
    icon: ShieldCheck,
  },
  PerformanceAnalysisAgent: {
    label: 'Performance Analysis',
    description: 'Deterministic pass rates, subject trends and the at-risk list.',
    icon: LineChart,
  },
  InterventionAgent: {
    label: 'Intervention Drafting',
    description: 'Drafts a support plan per at-risk student (pseudonymous data only).',
    icon: ClipboardCheck,
  },
  ReportingAgent: {
    label: 'Reporting',
    description: 'Generates the principal report as PDF and Excel.',
    icon: FileText,
  },
  Orchestrator: {
    label: 'Orchestrator',
    description: 'Wraps up the run and hands the drafts to a human for approval.',
    icon: Bot,
  },
}

export function agentMeta(name: string): AgentMeta {
  return AGENT_META[name] ?? { label: name, description: '', icon: Bot }
}

export const STEP_TONES: Record<AgentStepStatus, BadgeTone> = {
  pending: 'neutral',
  running: 'info',
  done: 'success',
  failed: 'danger',
  skipped: 'neutral',
}

export const STEP_LABELS: Record<AgentStepStatus, string> = {
  pending: 'Waiting',
  running: 'Running',
  done: 'Done',
  failed: 'Failed',
  skipped: 'Skipped',
}

export const RUN_TONES: Record<AgentRunStatus, BadgeTone> = {
  queued: 'neutral',
  running: 'info',
  awaiting_approval: 'warning',
  done: 'success',
  failed: 'danger',
}

export const RUN_LABELS: Record<AgentRunStatus, string> = {
  queued: 'Queued',
  running: 'Running',
  awaiting_approval: 'Awaiting approval',
  done: 'Done',
  failed: 'Failed',
}

export const LLM_MODE_LABELS: Record<string, string> = {
  llm: 'AI drafted (LLM)',
  template: 'Template mode (no LLM)',
  mixed: 'AI + template fallback',
  none: 'No plans drafted',
}

/** "850 ms", "2.4 s", "1 min 5 s". */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${ms} ms`
  const seconds = ms / 1000
  if (seconds < 60) return `${seconds.toFixed(1)} s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes} min ${Math.round(seconds - minutes * 60)} s`
}

/** "at_risk_by_severity" -> "At risk by severity". */
export function humanizeKey(key: string): string {
  const text = key.replace(/_/g, ' ').replace(/\bpct\b/, '%').trim()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function formatCost(value: string | number | null | undefined): string {
  const n = typeof value === 'number' ? value : Number(value ?? 0)
  if (!Number.isFinite(n) || n === 0) return '$0.00'
  return n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`
}

export interface Highlight {
  label: string
  value: string
}

type Formatter = (value: JsonValue) => string

const plain: Formatter = (v) => String(v)
const pct: Formatter = (v) => `${Number(v).toFixed(1)}%`
const count: Formatter = (v) => (Array.isArray(v) ? String(v.length) : '0')
const mode: Formatter = (v) => LLM_MODE_LABELS[String(v)] ?? String(v)
const cost: Formatter = (v) => formatCost(typeof v === 'number' || typeof v === 'string' ? v : 0)

const HIGHLIGHTS: Record<string, [string, string, Formatter][]> = {
  DataQualityAgent: [
    ['students', 'Students', plain],
    ['marks_recorded', 'Marks', plain],
    ['completeness_pct', 'Complete', pct],
    ['missing', 'Missing', plain],
  ],
  PerformanceAnalysisAgent: [
    ['pass_percentage', 'Pass rate', pct],
    ['mean_percentage', 'Mean', pct],
    ['at_risk_total', 'At risk', plain],
  ],
  InterventionAgent: [
    ['plans_created', 'Plans drafted', plain],
    ['mode', 'Mode', mode],
    ['tokens', 'Tokens', plain],
    ['skipped_existing', 'Already planned', plain],
  ],
  ReportingAgent: [['reports', 'Reports', count]],
  Orchestrator: [
    ['draft_plans', 'Drafts to review', plain],
    ['cost_usd', 'LLM cost', cost],
  ],
}

/** The headline numbers shown on a timeline step. */
export function stepHighlights(agentName: string, output: JsonObject | null): Highlight[] {
  if (!output) return []
  const spec = HIGHLIGHTS[agentName] ?? []
  const out: Highlight[] = []
  for (const [key, label, fmt] of spec) {
    const value = output[key]
    if (value !== undefined && value !== null) out.push({ label, value: fmt(value) })
  }
  return out
}
