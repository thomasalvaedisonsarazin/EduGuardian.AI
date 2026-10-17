import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { agentKeys } from '@/hooks/useAgentRuns'
import { useActiveSchoolId } from '@/hooks/useSession'
import { interventionService } from '@/services/interventionService'
import type { ID } from '@/types'
import type { InterventionFilters, InterventionUpdateInput } from '@/types/interventions'

export const interventionKeys = {
  all: (schoolId: ID | null) => ['interventions', schoolId] as const,
  list: (schoolId: ID | null, filters: InterventionFilters) => ['interventions', schoolId, 'list', filters] as const,
}

export function useInterventions(filters: InterventionFilters) {
  const schoolId = useActiveSchoolId()
  return useQuery({
    queryKey: interventionKeys.list(schoolId, filters),
    queryFn: () => interventionService.list(filters),
  })
}

export type InterventionAction =
  | { type: 'approve'; id: ID }
  | { type: 'reject'; id: ID; reason?: string }
  | { type: 'update'; id: ID; input: InterventionUpdateInput }
  | { type: 'status'; id: ID; status: 'in_progress' | 'completed' }

function perform(action: InterventionAction) {
  switch (action.type) {
    case 'approve':
      return interventionService.approve(action.id)
    case 'reject':
      return interventionService.reject(action.id, action.reason)
    case 'update':
      return interventionService.update(action.id, action.input)
    case 'status':
      return interventionService.setStatus(action.id, action.status)
  }
}

/** One mutation for every review action; refreshes the queue and agent runs afterwards. */
export function useInterventionAction() {
  const schoolId = useActiveSchoolId()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: perform,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: interventionKeys.all(schoolId) })
      void queryClient.invalidateQueries({ queryKey: agentKeys.all(schoolId) })
    },
  })
}
