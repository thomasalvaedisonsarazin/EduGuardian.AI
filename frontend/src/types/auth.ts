/** Module 1 (Auth & Tenancy) request/response types beyond the shared ones in `@/types`. */
import type { ID, ISODateTime, Membership, MeResponse, Role, School } from '@/types'

/** POST /auth/register. `school_code` is optional; the server derives a unique one from the name. */
export interface RegisterPayload {
  email: string
  password: string
  full_name: string
  school_name: string
  school_code?: string
}

/** A membership returned by GET /auth/me always includes its school. */
export interface MembershipWithSchool extends Membership {
  school: School
}

export interface AuthUser extends Omit<MeResponse, 'memberships'> {
  memberships: MembershipWithSchool[]
}

/** GET /schools/current/members item (membership flattened with the user's public fields). */
export interface SchoolMember {
  /** Membership id (use it for PATCH/DELETE). */
  id: ID
  user_id: ID
  school_id: ID
  role: Role
  email: string
  full_name: string
  is_active: boolean
  created_at: ISODateTime
}

/** POST /schools/current/members. Omit `password` to have the server generate a temporary one. */
export interface AddMemberPayload {
  email: string
  full_name: string
  role: Role
  password?: string
}

export interface AddMemberResult extends SchoolMember {
  user_created: boolean
  /** Returned once, only when the server generated it. */
  temporary_password: string | null
}

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

export const ROLE_LABELS: Record<Role, string> = {
  school_admin: 'School admin',
  principal: 'Principal',
  coordinator: 'Coordinator',
  teacher: 'Teacher',
}
