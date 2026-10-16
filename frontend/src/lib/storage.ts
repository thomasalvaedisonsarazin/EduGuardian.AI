/**
 * Session storage for auth tokens and the active school.
 * Every localStorage access is wrapped in try/catch: storage can be unavailable
 * (private mode, blocked site data) and the app must still render.
 */
import type { ID, TokenPair } from '@/types'

const KEYS = {
  access: 'eg.access_token',
  refresh: 'eg.refresh_token',
  school: 'eg.active_school_id',
} as const

/** Fired on window whenever the stored session changes (tokens or active school). */
export const SESSION_CHANGED_EVENT = 'eg:session-changed'

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    /* storage unavailable: session lives only in memory for this tab */
  }
}

function notify(): void {
  try {
    window.dispatchEvent(new Event(SESSION_CHANGED_EVENT))
  } catch {
    /* non-browser environment */
  }
}

export function getAccessToken(): string | null {
  return read(KEYS.access)
}

export function getRefreshToken(): string | null {
  return read(KEYS.refresh)
}

export function setTokens(tokens: Pick<TokenPair, 'access_token' | 'refresh_token'>): void {
  write(KEYS.access, tokens.access_token)
  write(KEYS.refresh, tokens.refresh_token)
  notify()
}

export function clearTokens(): void {
  write(KEYS.access, null)
  write(KEYS.refresh, null)
  notify()
}

export function getActiveSchoolId(): ID | null {
  const raw = read(KEYS.school)
  if (raw === null) return null
  const id = Number.parseInt(raw, 10)
  return Number.isFinite(id) ? id : null
}

export function setActiveSchoolId(id: ID | null): void {
  write(KEYS.school, id === null ? null : String(id))
  notify()
}

/** Clears tokens and active school (logout / failed refresh). */
export function clearSession(): void {
  write(KEYS.access, null)
  write(KEYS.refresh, null)
  write(KEYS.school, null)
  notify()
}

export function hasSession(): boolean {
  return getAccessToken() !== null
}
