import type { ReactNode } from 'react'
import type { Role } from '@/types'

export interface ProtectedRouteProps {
  children: ReactNode
  /** Reserved for Module 1: restrict to these membership roles. */
  roles?: readonly Role[]
}

/**
 * Phase 1 placeholder: renders children unconditionally.
 * Module 1 (auth) will check the session via AuthContext, redirect to /login when signed out,
 * and enforce `roles` against the active membership.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  return <>{children}</>
}
