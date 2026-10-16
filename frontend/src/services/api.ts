/**
 * Axios client for the EduGuardian API.
 *
 * - Adds `Authorization: Bearer <access>` and `X-School-Id: <active school>` to every request.
 * - On 401, refreshes the token pair once (single-flight across concurrent requests) and retries.
 *   If refresh fails, clears the session and redirects to /login.
 * - `ApiError.from(err)` normalises backend errors shaped `{"error": {"code", "message"}}`.
 */
import axios, { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios'
import {
  clearSession,
  getAccessToken,
  getActiveSchoolId,
  getRefreshToken,
  setTokens,
} from '@/lib/storage'
import type { ApiErrorBody, JsonValue, TokenPair } from '@/types'

export const API_ORIGIN: string = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')
export const API_BASE_URL = `${API_ORIGIN}/api/v1`

export const SCHOOL_HEADER = 'X-School-Id'

/** Endpoints that must never trigger the refresh-and-retry flow. */
const AUTH_PATHS_WITHOUT_REFRESH = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout']

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { Accept: 'application/json' },
  timeout: 30_000,
})

api.interceptors.request.use((config) => {
  const headers = AxiosHeaders.from(config.headers)
  const token = getAccessToken()
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
  const schoolId = getActiveSchoolId()
  if (schoolId !== null && !headers.has(SCHOOL_HEADER)) headers.set(SCHOOL_HEADER, String(schoolId))
  config.headers = headers
  return config
})

let refreshPromise: Promise<string | null> | null = null

/** Exchanges the stored refresh token for a new pair. Resolves the new access token or null. */
export function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise
  const refreshToken = getRefreshToken()
  if (!refreshToken) return Promise.resolve(null)

  refreshPromise = axios
    .post<TokenPair>(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken }, { timeout: 15_000 })
    .then(({ data }) => {
      setTokens(data)
      return data.access_token
    })
    .catch(() => null)
    .finally(() => {
      refreshPromise = null
    })
  return refreshPromise
}

function redirectToLogin(): void {
  if (typeof window === 'undefined') return
  const { pathname, search } = window.location
  if (pathname === '/login' || pathname === '/register') return
  const next = encodeURIComponent(`${pathname}${search}`)
  window.location.assign(`/login?next=${next}`)
}

function isAuthPath(url: string | undefined): boolean {
  if (!url) return false
  return AUTH_PATHS_WITHOUT_REFRESH.some((p) => url.includes(p))
}

api.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error) || !error.config) return Promise.reject(error)
    const original = error.config as RetriableConfig

    if (error.response?.status !== 401 || original._retry || isAuthPath(original.url)) {
      return Promise.reject(error)
    }

    original._retry = true
    const newToken = await refreshAccessToken()
    if (!newToken) {
      clearSession()
      redirectToLogin()
      return Promise.reject(error)
    }

    const headers = AxiosHeaders.from(original.headers)
    headers.set('Authorization', `Bearer ${newToken}`)
    original.headers = headers
    return api(original)
  },
)

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false
  const inner = (value as { error: unknown }).error
  return (
    typeof inner === 'object' &&
    inner !== null &&
    typeof (inner as { code?: unknown }).code === 'string' &&
    typeof (inner as { message?: unknown }).message === 'string'
  )
}

/** FastAPI's default validation/HTTPException body: {"detail": string | [{msg}]} */
function detailMessage(value: unknown): string | null {
  if (typeof value !== 'object' || value === null || !('detail' in value)) return null
  const detail = (value as { detail: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first: unknown = detail[0]
    if (typeof first === 'object' && first !== null && 'msg' in first) {
      return String((first as { msg: unknown }).msg)
    }
  }
  return null
}

export class ApiError extends Error {
  readonly code: string
  readonly status: number | null
  readonly details: JsonValue | undefined

  constructor(message: string, code: string, status: number | null, details?: JsonValue) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }

  /** Normalises any thrown value (AxiosError, Error, unknown) into an ApiError. */
  static from(err: unknown): ApiError {
    if (err instanceof ApiError) return err
    if (err instanceof AxiosError) {
      const status = err.response?.status ?? null
      const body: unknown = err.response?.data
      if (isApiErrorBody(body)) {
        return new ApiError(body.error.message, body.error.code, status, body.error.details)
      }
      const detail = detailMessage(body)
      if (detail) return new ApiError(detail, status === 422 ? 'validation_error' : 'http_error', status)
      if (!err.response) {
        return new ApiError('Cannot reach the server. Check your connection and try again.', 'network_error', null)
      }
      return new ApiError(err.message || 'Request failed', 'http_error', status)
    }
    if (err instanceof Error) return new ApiError(err.message, 'unknown_error', null)
    return new ApiError('Something went wrong', 'unknown_error', null)
  }
}

/** Convenience: user-facing message for any error. */
export function getErrorMessage(err: unknown): string {
  return ApiError.from(err).message
}

export default api
