import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useId, useState } from 'react'
import { agentMeta, humanizeKey } from '@/components/agents/agentMeta'
import { AuditTable } from '@/components/audit'
import { GradientButton, PageWrapper } from '@/components/ui'
import { useAuditLogs } from '@/hooks/useAudit'
import { getErrorMessage } from '@/services/api'

const PAGE_SIZE = 50

const selectClass =
  'h-10 rounded-xl border border-slate-200 bg-white/80 px-3 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-100'

export default function AuditPage() {
  const ids = useId()
  const [actor, setActor] = useState('')
  const [entityType, setEntityType] = useState('')
  const [page, setPage] = useState(0)

  const logs = useAuditLogs({
    actor: actor || undefined,
    entity_type: entityType || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  })
  const total = logs.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const agentActors = (logs.data?.actors ?? []).filter((a) => a !== 'user')

  return (
    <PageWrapper title="Audit Log" description="Every agent step, calculation summary, approval and edit — newest first.">
      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label htmlFor={`${ids}-actor`} className="block text-xs font-medium text-slate-500">
            Actor
          </label>
          <select
            id={`${ids}-actor`}
            value={actor}
            onChange={(e) => {
              setActor(e.target.value)
              setPage(0)
            }}
            className={selectClass}
          >
            <option value="">Everyone</option>
            <option value="user">People</option>
            <option value="agents">All agents</option>
            {agentActors.map((a) => (
              <option key={a} value={a}>
                {agentMeta(a).label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor={`${ids}-entity`} className="block text-xs font-medium text-slate-500">
            Entity
          </label>
          <select
            id={`${ids}-entity`}
            value={entityType}
            onChange={(e) => {
              setEntityType(e.target.value)
              setPage(0)
            }}
            className={selectClass}
          >
            <option value="">All entities</option>
            {(logs.data?.entity_types ?? []).map((t) => (
              <option key={t} value={t}>
                {humanizeKey(t)}
              </option>
            ))}
          </select>
        </div>
        <p className="ml-auto text-sm text-slate-500 dark:text-slate-400">{total.toLocaleString()} entries</p>
      </div>

      {logs.isError && (
        <p role="alert" className="mb-4 text-sm text-rose-600">
          {getErrorMessage(logs.error)}
        </p>
      )}
      <AuditTable entries={logs.data?.items ?? []} loading={logs.isLoading} />

      <div className="mt-4 flex items-center justify-end gap-2">
        <GradientButton
          variant="ghost"
          size="sm"
          icon={ChevronLeft}
          disabled={page === 0}
          onClick={() => setPage((p) => Math.max(0, p - 1))}
        >
          Newer
        </GradientButton>
        <span className="text-sm text-slate-500 tabular-nums">
          Page {page + 1} of {pages}
        </span>
        <GradientButton
          variant="ghost"
          size="sm"
          iconRight={ChevronRight}
          disabled={page + 1 >= pages}
          onClick={() => setPage((p) => p + 1)}
        >
          Older
        </GradientButton>
      </div>
    </PageWrapper>
  )
}
