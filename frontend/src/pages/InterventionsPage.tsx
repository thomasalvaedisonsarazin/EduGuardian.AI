import { ClipboardCheck, X } from 'lucide-react'
import { useId } from 'react'
import { useSearchParams } from 'react-router-dom'
import { InterventionCard, STATUS_LABELS, STATUS_ORDER } from '@/components/interventions'
import { Badge, EmptyState, PageWrapper, Spinner } from '@/components/ui'
import { parseId, useExamList } from '@/hooks/useAnalytics'
import { useInterventionAction, useInterventions } from '@/hooks/useInterventions'
import { useClasses } from '@/hooks/useSetup'
import { getErrorMessage } from '@/services/api'
import { cn } from '@/lib/cn'
import type { InterventionStatus } from '@/types'
import type { InterventionFilters } from '@/types/interventions'

function parseStatus(raw: string | null): InterventionStatus {
  return STATUS_ORDER.includes(raw as InterventionStatus) ? (raw as InterventionStatus) : 'draft'
}

const selectClass =
  'h-10 rounded-xl border border-slate-200 bg-white/80 px-3 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-100'

export default function InterventionsPage() {
  const ids = useId()
  const [params, setParams] = useSearchParams()
  const status = parseStatus(params.get('status'))
  const runId = parseId(params.get('run_id') ?? undefined)
  const classId = parseId(params.get('class_section_id') ?? undefined)
  const examId = parseId(params.get('exam_id') ?? undefined)

  const filters: InterventionFilters = {
    status,
    ...(runId !== null && { run_id: runId }),
    ...(classId !== null && { class_section_id: classId }),
    ...(examId !== null && { exam_id: examId }),
  }
  const list = useInterventions(filters)
  const classes = useClasses()
  const exams = useExamList()
  const action = useInterventionAction()
  const busyId = action.isPending ? action.variables?.id : undefined

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params)
    if (value === null || value === '') next.delete(key)
    else next.set(key, value)
    setParams(next)
  }

  const counts = list.data?.counts ?? {}

  return (
    <PageWrapper
      title="Interventions"
      description="Review AI-drafted support plans. Nothing reaches a student until a teacher or coordinator approves it."
    >
      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label htmlFor={`${ids}-class`} className="block text-xs font-medium text-slate-500">
            Class
          </label>
          <select
            id={`${ids}-class`}
            value={classId ?? ''}
            onChange={(e) => setParam('class_section_id', e.target.value)}
            className={selectClass}
          >
            <option value="">All classes</option>
            {(classes.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.grade}-{c.section}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor={`${ids}-exam`} className="block text-xs font-medium text-slate-500">
            Exam
          </label>
          <select
            id={`${ids}-exam`}
            value={examId ?? ''}
            onChange={(e) => setParam('exam_id', e.target.value)}
            className={selectClass}
          >
            <option value="">All exams</option>
            {(exams.data ?? []).map((e) => (
              <option key={e.exam.id} value={e.exam.id}>
                {e.exam.name}
              </option>
            ))}
          </select>
        </div>
        {runId !== null && (
          <button
            type="button"
            onClick={() => setParam('run_id', null)}
            className="inline-flex h-10 cursor-pointer items-center gap-1.5 rounded-full bg-brand-50 px-3 text-sm text-brand-700 hover:bg-brand-100 dark:bg-brand-950 dark:text-brand-300"
          >
            Run #{runId}
            <X aria-label="Clear run filter" className="size-4" />
          </button>
        )}
      </div>

      <div role="tablist" aria-label="Plan status" className="mb-5 flex flex-wrap gap-2">
        {STATUS_ORDER.map((s) => (
          <button
            key={s}
            type="button"
            role="tab"
            aria-selected={s === status}
            onClick={() => setParam('status', s)}
            className={cn(
              'inline-flex cursor-pointer items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium transition-colors',
              s === status
                ? 'bg-gradient-to-r from-brand-600 to-accent-500 text-white shadow'
                : 'bg-white text-slate-600 hover:bg-slate-100 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800',
            )}
          >
            {STATUS_LABELS[s]}
            <Badge tone={s === status ? 'neutral' : 'brand'}>{counts[s] ?? 0}</Badge>
          </button>
        ))}
      </div>

      {action.isError && (
        <p role="alert" className="mb-4 text-sm text-rose-600 dark:text-rose-400">
          {getErrorMessage(action.error)}
        </p>
      )}
      {list.isLoading && <Spinner showLabel label="Loading plans" />}
      {list.isError && (
        <p role="alert" className="text-sm text-rose-600">
          {getErrorMessage(list.error)}
        </p>
      )}
      {list.data && list.data.items.length === 0 && (
        <EmptyState
          icon={ClipboardCheck}
          title={`No ${STATUS_LABELS[status].toLowerCase()} plans`}
          description="Run the agents from the AI Agents page to draft plans for at-risk students."
        />
      )}
      <div className="space-y-4">
        {list.data?.items.map((item) => (
          <InterventionCard
            key={item.id}
            item={item}
            busy={busyId === item.id}
            onApprove={(id) => action.mutate({ type: 'approve', id })}
            onReject={(id, reason) => action.mutate({ type: 'reject', id, reason })}
            onSave={(id, input) => action.mutate({ type: 'update', id, input })}
            onStatus={(id, next) => action.mutate({ type: 'status', id, status: next })}
          />
        ))}
      </div>
      {list.data && list.data.total > list.data.items.length && (
        <p className="mt-4 text-sm text-slate-500">
          Showing {list.data.items.length} of {list.data.total} plans. Narrow the filters to see the rest.
        </p>
      )}
    </PageWrapper>
  )
}
