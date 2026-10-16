import { ApiError } from '@/services/api'

export type FieldErrors<K extends string> = Partial<Record<K, string>>

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function isValidEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim())
}

/**
 * Maps a backend 422 `details` array (`[{loc: ["body", "email"], msg}]`) onto form fields.
 * Unknown fields are ignored; returns an empty object for other errors.
 */
export function fieldErrorsFromApi<K extends string>(err: unknown, fields: readonly K[]): FieldErrors<K> {
  const { details } = ApiError.from(err)
  const out: FieldErrors<K> = {}
  if (!Array.isArray(details)) return out
  for (const item of details) {
    if (typeof item !== 'object' || item === null || Array.isArray(item)) continue
    const loc = item.loc
    const msg = item.msg
    if (!Array.isArray(loc) || typeof msg !== 'string') continue
    const field = loc[loc.length - 1]
    const match = fields.find((f) => f === field)
    if (match && !out[match]) out[match] = msg.replace(/^Value error, /, '')
  }
  return out
}

/** Only allow same-origin relative paths as post-login redirect targets. */
export function safeNextPath(next: string | null, fallback = '/dashboard'): string {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/login') || next.startsWith('/register')) {
    return fallback
  }
  return next
}
