import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, type ReactNode } from 'react'
import { useActiveSchoolId, useHasSession } from '@/hooks/useSession'
import { clearSession, getActiveSchoolId, setActiveSchoolId, setTokens } from '@/lib/storage'
import { authService } from '@/services/authService'
import type { ID, LoginRequest, TokenPair } from '@/types'
import type { AuthStatus, AuthUser, RegisterPayload } from '@/types/auth'
import { AuthContext, ME_QUERY_KEY, type AuthContextValue } from './auth-context'

/** Keeps the stored active school valid for `user`: defaults to the first membership. */
function ensureActiveSchool(user: AuthUser): void {
  const current = getActiveSchoolId()
  const ids = user.memberships.map((m) => m.school_id)
  if (current !== null && (ids.includes(current) || user.is_superadmin)) return
  const next = ids[0] ?? null
  if (next !== current) setActiveSchoolId(next)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const hasSession = useHasSession()
  const activeSchoolId = useActiveSchoolId()

  const meQuery = useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: authService.getMe,
    enabled: hasSession,
    staleTime: 5 * 60_000,
    retry: false,
  })

  const user: AuthUser | null = hasSession ? (meQuery.data ?? null) : null
  const status: AuthStatus = !hasSession
    ? 'unauthenticated'
    : user
      ? 'authenticated'
      : meQuery.isPending
        ? 'loading'
        : 'unauthenticated'

  useEffect(() => {
    if (user) ensureActiveSchool(user)
  }, [user, activeSchoolId])

  const establishSession = useCallback(
    async (tokens: TokenPair): Promise<AuthUser> => {
      setTokens(tokens)
      const me = await queryClient.fetchQuery({ queryKey: ME_QUERY_KEY, queryFn: authService.getMe, staleTime: 0 })
      ensureActiveSchool(me)
      return me
    },
    [queryClient],
  )

  const login = useCallback(
    async (credentials: LoginRequest) => establishSession(await authService.login(credentials)),
    [establishSession],
  )

  const register = useCallback(
    async (payload: RegisterPayload) => {
      // A brand-new account owns exactly one school: make it active.
      setActiveSchoolId(null)
      return establishSession(await authService.register(payload))
    },
    [establishSession],
  )

  const logout = useCallback(async () => {
    try {
      await authService.logout()
    } catch {
      /* the session is cleared locally regardless */
    }
    clearSession()
    queryClient.clear()
  }, [queryClient])

  const switchSchool = useCallback(
    (schoolId: ID) => {
      if (schoolId === getActiveSchoolId()) return
      setActiveSchoolId(schoolId)
      // Drop every tenant-scoped cache entry; active queries refetch with the new X-School-Id.
      void queryClient.resetQueries({ predicate: (q) => q.queryKey[0] !== ME_QUERY_KEY[0] })
    },
    [queryClient],
  )

  const refreshUser = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ME_QUERY_KEY })
  }, [queryClient])

  const value = useMemo<AuthContextValue>(() => {
    const memberships = user?.memberships ?? []
    const activeMembership = memberships.find((m) => m.school_id === activeSchoolId) ?? null
    const role = activeMembership?.role ?? (user?.is_superadmin && activeSchoolId !== null ? 'school_admin' : null)
    return {
      status,
      isLoading: status === 'loading',
      isAuthenticated: status === 'authenticated',
      user,
      memberships,
      activeMembership,
      activeSchoolId,
      role,
      login,
      register,
      logout,
      switchSchool,
      refreshUser,
    }
  }, [status, user, activeSchoolId, login, register, logout, switchSchool, refreshUser])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
