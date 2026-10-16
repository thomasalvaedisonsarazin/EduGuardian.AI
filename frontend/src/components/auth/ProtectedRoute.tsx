import { ShieldAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { EmptyState } from '@/components/ui/EmptyState'
import { GlassCard } from '@/components/ui/GlassCard'
import { PageSpinner } from '@/components/ui/Spinner'
import { useAuth } from '@/hooks/useAuth'
import type { Role } from '@/types'
import { ROLE_LABELS } from '@/types/auth'

export interface ProtectedRouteProps {
  children: ReactNode
  /** Restrict to these roles in the active school (superadmins always pass). */
  roles?: readonly Role[]
}

/**
 * Gate for authenticated routes: spinner while the session loads, redirect to
 * `/login?next=<current path>` when signed out, friendly "no access" state when the
 * active-school role is not in `roles`.
 */
export function ProtectedRoute({ children, roles }: ProtectedRouteProps) {
  const { status, user, role } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <PageSpinner label="Checking your session" />

  if (status === 'unauthenticated' || !user) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`)
    return <Navigate to={`/login?next=${next}`} replace />
  }

  if (roles && roles.length > 0 && !user.is_superadmin && (role === null || !roles.includes(role))) {
    return (
      <GlassCard hoverable={false} className="mx-auto mt-10 max-w-lg">
        <EmptyState
          icon={ShieldAlert}
          title="You don't have access to this page"
          description={`This area is available to: ${roles.map((r) => ROLE_LABELS[r]).join(', ')}. Ask your school admin if you need access.`}
          action={
            <Link to="/dashboard" className="text-sm font-semibold text-brand-600 hover:underline dark:text-brand-400">
              Back to dashboard
            </Link>
          }
        />
      </GlassCard>
    )
  }

  return <>{children}</>
}
