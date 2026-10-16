/** Auth & school-membership API calls (Module 1). */
import api from '@/services/api'
import type { ID, LoginRequest, Role, School, TokenPair } from '@/types'
import type {
  AddMemberPayload,
  AddMemberResult,
  AuthUser,
  RegisterPayload,
  SchoolMember,
} from '@/types/auth'

export const authService = {
  async login(payload: LoginRequest): Promise<TokenPair> {
    const { data } = await api.post<TokenPair>('/auth/login', payload)
    return data
  },

  async register(payload: RegisterPayload): Promise<TokenPair> {
    const body: RegisterPayload = { ...payload }
    if (!body.school_code?.trim()) delete body.school_code
    const { data } = await api.post<TokenPair>('/auth/register', body)
    return data
  },

  async logout(refreshToken: string): Promise<void> {
    await api.post('/auth/logout', { refresh_token: refreshToken })
  },

  async getMe(): Promise<AuthUser> {
    const { data } = await api.get<AuthUser>('/auth/me')
    return data
  },
}

/** Active-school endpoints (X-School-Id is added by the api client). */
export const schoolService = {
  async getCurrentSchool(): Promise<School> {
    const { data } = await api.get<School>('/schools/current')
    return data
  },

  async listMembers(): Promise<SchoolMember[]> {
    const { data } = await api.get<SchoolMember[]>('/schools/current/members')
    return data
  },

  async addMember(payload: AddMemberPayload): Promise<AddMemberResult> {
    const { data } = await api.post<AddMemberResult>('/schools/current/members', payload)
    return data
  },

  async updateMemberRole(membershipId: ID, role: Role): Promise<SchoolMember> {
    const { data } = await api.patch<SchoolMember>(`/schools/current/members/${membershipId}`, { role })
    return data
  },

  async removeMember(membershipId: ID): Promise<void> {
    await api.delete(`/schools/current/members/${membershipId}`)
  },
}
