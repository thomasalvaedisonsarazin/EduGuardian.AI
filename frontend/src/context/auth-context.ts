import { createContext } from 'react'
import type { ID, LoginRequest, Role } from '@/types'
import type { AuthStatus, AuthUser, MembershipWithSchool, RegisterPayload } from '@/types/auth'

/** React Query key for GET /auth/me. Excluded from the cache reset on school switch. */
export const ME_QUERY_KEY = ['auth', 'me'] as const

export interface AuthContextValue {
  status: AuthStatus
  isLoading: boolean
  isAuthenticated: boolean
  user: AuthUser | null
  memberships: MembershipWithSchool[]
  /** Membership for the active school (null for a superadmin browsing without membership). */
  activeMembership: MembershipWithSchool | null
  activeSchoolId: ID | null
  /** Role in the active school; superadmins act as `school_admin`. */
  role: Role | null
  login: (credentials: LoginRequest) => Promise<AuthUser>
  register: (payload: RegisterPayload) => Promise<AuthUser>
  logout: () => Promise<void>
  switchSchool: (schoolId: ID) => void
  refreshUser: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)
