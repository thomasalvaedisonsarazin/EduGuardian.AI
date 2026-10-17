/** Typed client for /api/v1/agent-runs. */
import api from '@/services/api'
import type { ID } from '@/types'
import type { AgentRunDetail, AgentRunList, StartRunInput } from '@/types/agents'

export const agentService = {
  async startRun(input: StartRunInput): Promise<AgentRunDetail> {
    const { data } = await api.post<AgentRunDetail>('/agent-runs', input)
    return data
  },

  async listRuns(limit = 20): Promise<AgentRunList> {
    const { data } = await api.get<AgentRunList>('/agent-runs', { params: { limit } })
    return data
  },

  async getRun(runId: ID): Promise<AgentRunDetail> {
    const { data } = await api.get<AgentRunDetail>(`/agent-runs/${runId}`)
    return data
  },
}

export type AgentService = typeof agentService
