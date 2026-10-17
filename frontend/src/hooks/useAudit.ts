import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useActiveSchoolId } from '@/hooks/useSession'
import { auditService } from '@/services/auditService'
import type { ID } from '@/types'
import type { AuditFilters } from '@/types/audit'

export const auditKeys = {
  list: (schoolId: ID | null, filters: AuditFilters) => ['audit', schoolId, filters] as const,
}

export function useAuditLogs(filters: AuditFilters) {
  const schoolId = useActiveSchoolId()
  return useQuery({
    queryKey: auditKeys.list(schoolId, filters),
    queryFn: () => auditService.list(filters),
    placeholderData: keepPreviousData,
  })
}
