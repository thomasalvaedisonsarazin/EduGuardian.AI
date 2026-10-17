import { Bot } from 'lucide-react'
import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AgentStepTimeline, RunAnalysisCard, RunHistory, RunStatusBanner, type ClassOption } from '@/components/agents'
import { EmptyState, GlassCard, PageWrapper, Spinner } from '@/components/ui'
import { parseId, useExamList } from '@/hooks/useAnalytics'
import { useRun, useRunList, useStartRun } from '@/hooks/useAgentRuns'
import { useAuth } from '@/hooks/useAuth'
import { useClasses } from '@/hooks/useSetup'
import { getErrorMessage } from '@/services/api'
import type { ID, Role } from '@/types'

const RUNNER_ROLES: readonly Role[] = ['school_admin', 'principal', 'coordinator']

export default function AgentsPage() {
  const [params, setParams] = useSearchParams()
  const runParam = parseId(params.get('run') ?? undefined)
  const { role } = useAuth()
  const canRun = role !== null && RUNNER_ROLES.includes(role)

  const exams = useExamList()
  const classes = useClasses()
  const runs = useRunList()
  const start = useStartRun()

  const selectedId: ID | null = runParam ?? runs.data?.items[0]?.id ?? null
  const run = useRun(selectedId)

  const classOptions: ClassOption[] = useMemo(
    () =>
      (classes.data ?? [])
        .map((c) => ({ id: c.id, label: `${c.grade}-${c.section}` }))
        .sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true })),
    [classes.data],
  )

  const selectRun = (id: ID) => setParams({ run: String(id) })

  const handleStart = (examId: ID, classSectionIds: ID[]) => {
    start.mutate(
      { exam_id: examId, class_section_ids: classSectionIds.length > 0 ? classSectionIds : null },
      { onSuccess: (created) => selectRun(created.id) },
    )
  }

  return (
    <PageWrapper
      title="AI Agents"
      description="A transparent multi-agent workflow: every step, number and draft is recorded and needs human approval."
    >
      <div className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_1fr]">
        <div className="space-y-6">
          {canRun ? (
            <RunAnalysisCard
              exams={exams.data ?? []}
              classes={classOptions}
              loading={exams.isLoading}
              starting={start.isPending}
              error={start.isError ? getErrorMessage(start.error) : null}
              onStart={handleStart}
            />
          ) : (
            <GlassCard hoverable={false}>
              <p className="text-sm text-slate-600 dark:text-slate-300">
                Analysis runs are started by school admins, principals and coordinators. You can follow their
                progress here and review the plans for your classes on the Interventions page.
              </p>
            </GlassCard>
          )}
        </div>

        <GlassCard hoverable={false} className="min-w-0 space-y-6">
          {selectedId === null && !runs.isLoading && (
            <EmptyState
              icon={Bot}
              title="No agent runs yet"
              description="Pick an exam and start the agents to see each step appear here live."
            />
          )}
          {(runs.isLoading || (selectedId !== null && run.isLoading)) && <Spinner showLabel label="Loading run" />}
          {run.isError && (
            <p role="alert" className="text-sm text-rose-600">
              {getErrorMessage(run.error)}
            </p>
          )}
          {run.data && (
            <>
              <RunStatusBanner run={run.data} />
              <AgentStepTimeline steps={run.data.steps} runStatus={run.data.status} />
            </>
          )}
        </GlassCard>
      </div>

      <section className="mt-8 space-y-3">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Run history</h2>
        <RunHistory runs={runs.data?.items ?? []} loading={runs.isLoading} selectedId={selectedId} onSelect={selectRun} />
      </section>
    </PageWrapper>
  )
}
