/** Typed client for /api/v1/audit-logs. */
import api from '@/services/api'
import type { AuditFilters, AuditList } from '@/types/audit'

export const auditService = {
  async list(filters: AuditFilters = {}): Promise<AuditList> {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== undefined && v !== ''))
    const { data } = await api.get<AuditList>('/audit-logs', { params })
    return data
  },
}

export type AuditService = typeof auditService
