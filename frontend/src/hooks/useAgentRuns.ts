import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useActiveSchoolId } from '@/hooks/useSession'
import { agentService } from '@/services/agentService'
import type { AgentRunStatus, ID } from '@/types'
import type { StartRunInput } from '@/types/agents'

export const POLL_INTERVAL_MS = 1500

export const agentKeys = {
  all: (schoolId: ID | null) => ['agent-runs', schoolId] as const,
  list: (schoolId: ID | null) => ['agent-runs', schoolId, 'list'] as const,
  detail: (schoolId: ID | null, runId: ID) => ['agent-runs', schoolId, 'detail', runId] as const,
}

export function isActiveStatus(status: AgentRunStatus | undefined): boolean {
  return status === 'queued' || status === 'running'
}

export function useRunList() {
  const schoolId = useActiveSchoolId()
  return useQuery({ queryKey: agentKeys.list(schoolId), queryFn: () => agentService.listRuns() })
}

/** Polls every 1.5 s while the run is queued or running. */
export function useRun(runId: ID | null) {
  const schoolId = useActiveSchoolId()
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: agentKeys.detail(schoolId, runId ?? 0),
    queryFn: async () => {
      const run = await agentService.getRun(runId ?? 0)
      if (!isActiveStatus(run.status)) {
        void queryClient.invalidateQueries({ queryKey: agentKeys.list(schoolId) })
      }
      return run
    },
    enabled: runId !== null,
    refetchInterval: (query) => (isActiveStatus(query.state.data?.status) ? POLL_INTERVAL_MS : false),
  })
}

export function useStartRun() {
  const schoolId = useActiveSchoolId()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: StartRunInput) => agentService.startRun(input),
    onSuccess: (run) => {
      queryClient.setQueryData(agentKeys.detail(schoolId, run.id), run)
      void queryClient.invalidateQueries({ queryKey: agentKeys.list(schoolId) })
    },
  })
}
