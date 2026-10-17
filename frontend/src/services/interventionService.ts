/** Typed client for /api/v1/interventions. */
import api from '@/services/api'
import type { ID } from '@/types'
import type {
  InterventionFilters,
  InterventionItem,
  InterventionList,
  InterventionUpdateInput,
} from '@/types/interventions'

export const interventionService = {
  async list(filters: InterventionFilters = {}): Promise<InterventionList> {
    const { data } = await api.get<InterventionList>('/interventions', { params: filters })
    return data
  },

  async get(id: ID): Promise<InterventionItem> {
    const { data } = await api.get<InterventionItem>(`/interventions/${id}`)
    return data
  },

  async update(id: ID, input: InterventionUpdateInput): Promise<InterventionItem> {
    const { data } = await api.put<InterventionItem>(`/interventions/${id}`, input)
    return data
  },

  async approve(id: ID): Promise<InterventionItem> {
    const { data } = await api.post<InterventionItem>(`/interventions/${id}/approve`)
    return data
  },

  async reject(id: ID, reason?: string): Promise<InterventionItem> {
    const { data } = await api.post<InterventionItem>(`/interventions/${id}/reject`, { reason: reason || null })
    return data
  },

  async setStatus(id: ID, status: 'in_progress' | 'completed'): Promise<InterventionItem> {
    const { data } = await api.patch<InterventionItem>(`/interventions/${id}/status`, { status })
    return data
  },
}

export type InterventionService = typeof interventionService
