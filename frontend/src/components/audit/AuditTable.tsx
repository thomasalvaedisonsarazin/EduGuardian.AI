import { Bot, ScrollText, User } from 'lucide-react'
import { agentMeta, humanizeKey } from '@/components/agents/agentMeta'
import { Badge, DataTable, EmptyState, type DataTableColumn } from '@/components/ui'
import type { JsonObject, JsonValue } from '@/types'
import type { AuditEntry } from '@/types/audit'

export interface AuditTableProps {
  entries: readonly AuditEntry[]
  loading?: boolean
}

const DETAIL_SKIP = new Set(['summary', 'input'])

function short(value: JsonValue): string {
  if (value === null) return '—'
  if (Array.isArray(value)) return value.map((v) => (typeof v === 'object' ? '…' : String(v))).join(', ')
  if (typeof value === 'object') return '…'
  return String(value)
}

/** Compact one-line description of an entry's detail JSON. */
function detailText(detail: JsonObject | null): string {
  if (!detail) return ''
  return Object.entries(detail)
    .filter(([key, value]) => !DETAIL_SKIP.has(key) && value !== null && typeof value !== 'object')
    .concat(Object.entries(detail).filter(([, value]) => Array.isArray(value)))
    .slice(0, 5)
    .map(([key, value]) => `${humanizeKey(key)}: ${short(value)}`)
    .join(' · ')
}

function ActorBadge({ entry }: { entry: AuditEntry }) {
  if (entry.actor === 'user') {
    return (
      <Badge tone="brand">
        <User aria-hidden className="size-3" />
        {entry.user_email ?? 'User'}
      </Badge>
    )
  }
  return (
    <Badge tone="accent">
      <Bot aria-hidden className="size-3" />
      {agentMeta(entry.actor).label}
    </Badge>
  )
}

export function AuditTable({ entries, loading = false }: AuditTableProps) {
  const columns: DataTableColumn<AuditEntry>[] = [
    {
      id: 'time',
      header: 'Time',
      className: 'whitespace-nowrap tabular-nums',
      cell: (e) => new Date(e.created_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'medium' }),
    },
    { id: 'actor', header: 'Actor', cell: (e) => <ActorBadge entry={e} /> },
    { id: 'action', header: 'Action', cell: (e) => humanizeKey(e.action) },
    {
      id: 'entity',
      header: 'Entity',
      className: 'whitespace-nowrap',
      cell: (e) => `${humanizeKey(e.entity_type)}${e.entity_id !== null ? ` #${e.entity_id}` : ''}`,
    },
    {
      id: 'detail',
      header: 'Details',
      className: 'max-w-md text-xs text-slate-500 dark:text-slate-400',
      cell: (e) => detailText(e.detail) || '—',
    },
  ]
  return (
    <DataTable
      caption="Audit log"
      columns={columns}
      rows={entries}
      getRowId={(e) => e.id}
      loading={loading}
      empty={<EmptyState icon={ScrollText} title="No audit entries" description="Nothing matches these filters yet." />}
      dense
    />
  )
}
