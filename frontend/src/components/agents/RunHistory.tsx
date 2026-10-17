import { History } from 'lucide-react'
import { Badge, DataTable, EmptyState, type DataTableColumn } from '@/components/ui'
import type { ID } from '@/types'
import type { AgentRunSummary } from '@/types/agents'
import { LLM_MODE_LABELS, RUN_LABELS, RUN_TONES, formatCost } from './agentMeta'

export interface RunHistoryProps {
  runs: readonly AgentRunSummary[]
  loading?: boolean
  selectedId?: ID | null
  onSelect: (runId: ID) => void
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function planSummary(counts: AgentRunSummary['plan_counts']): string {
  const total = Object.values(counts).reduce<number>((sum, n) => sum + (n ?? 0), 0)
  if (total === 0) return '—'
  const drafts = counts.draft ?? 0
  return drafts > 0 ? `${total} (${drafts} to review)` : String(total)
}

export function RunHistory({ runs, loading = false, selectedId, onSelect }: RunHistoryProps) {
  const columns: DataTableColumn<AgentRunSummary>[] = [
    {
      id: 'run',
      header: 'Run',
      cell: (r) => (
        <span className={r.id === selectedId ? 'font-semibold text-brand-700 dark:text-brand-300' : 'font-medium'}>#{r.id}</span>
      ),
    },
    { id: 'exam', header: 'Exam', cell: (r) => r.exam_name ?? '—' },
    { id: 'when', header: 'Started', cell: (r) => fmtTime(r.created_at) },
    {
      id: 'status',
      header: 'Status',
      cell: (r) => (
        <Badge tone={RUN_TONES[r.status]} dot>
          {RUN_LABELS[r.status]}
        </Badge>
      ),
    },
    { id: 'mode', header: 'Drafting', cell: (r) => (r.llm_mode ? (LLM_MODE_LABELS[r.llm_mode] ?? r.llm_mode) : '—') },
    { id: 'plans', header: 'Plans', align: 'right', cell: (r) => planSummary(r.plan_counts) },
    { id: 'cost', header: 'LLM cost', align: 'right', cell: (r) => formatCost(r.cost_usd) },
  ]
  return (
    <DataTable
      caption="Agent run history"
      columns={columns}
      rows={runs}
      getRowId={(r) => r.id}
      loading={loading}
      onRowClick={(r) => onSelect(r.id)}
      empty={<EmptyState icon={History} title="No runs yet" description="Start your first analysis above." />}
      dense
    />
  )
}
