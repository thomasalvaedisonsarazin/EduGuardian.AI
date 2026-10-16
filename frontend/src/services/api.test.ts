import { AxiosError, AxiosHeaders, type AxiosAdapter, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, describe, expect, it } from 'vitest'
import { setActiveSchoolId, setTokens } from '@/lib/storage'
import { API_BASE_URL, ApiError, SCHOOL_HEADER, api } from './api'

function makeResponse<T>(config: InternalAxiosRequestConfig, status: number, data: T): AxiosResponse<T> {
  return { data, status, statusText: String(status), headers: {}, config }
}

afterEach(() => {
  window.localStorage.clear()
})

describe('api client', () => {
  it('uses the /api/v1 base URL', () => {
    expect(API_BASE_URL).toMatch(/\/api\/v1$/)
    expect(api.defaults.baseURL).toBe(API_BASE_URL)
  })

  it('adds Authorization and X-School-Id headers', async () => {
    setTokens({ access_token: 'tok', refresh_token: 'ref' })
    setActiveSchoolId(42)
    let seen: AxiosHeaders | undefined
    const adapter: AxiosAdapter = (config) => {
      seen = AxiosHeaders.from(config.headers)
      return Promise.resolve(makeResponse(config, 200, { ok: true }))
    }
    await api.get('/ping', { adapter })
    expect(seen?.get('Authorization')).toBe('Bearer tok')
    expect(seen?.get(SCHOOL_HEADER)).toBe('42')
  })

  it('omits headers when there is no session', async () => {
    let seen: AxiosHeaders | undefined
    const adapter: AxiosAdapter = (config) => {
      seen = AxiosHeaders.from(config.headers)
      return Promise.resolve(makeResponse(config, 200, {}))
    }
    await api.get('/ping', { adapter })
    expect(seen?.has('Authorization')).toBe(false)
    expect(seen?.has(SCHOOL_HEADER)).toBe(false)
  })
})

describe('ApiError.from', () => {
  const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig

  it('parses the backend error envelope', () => {
    const err = new AxiosError('Request failed', 'ERR_BAD_REQUEST', config, null, makeResponse(config, 404, {
      error: { code: 'not_found', message: 'Student not found' },
    }))
    const parsed = ApiError.from(err)
    expect(parsed).toBeInstanceOf(ApiError)
    expect(parsed.code).toBe('not_found')
    expect(parsed.message).toBe('Student not found')
    expect(parsed.status).toBe(404)
  })

  it('falls back to FastAPI detail messages', () => {
    const err = new AxiosError('x', 'ERR_BAD_REQUEST', config, null, makeResponse(config, 422, {
      detail: [{ msg: 'field required' }],
    }))
    const parsed = ApiError.from(err)
    expect(parsed.code).toBe('validation_error')
    expect(parsed.message).toBe('field required')
  })

  it('reports network errors', () => {
    const parsed = ApiError.from(new AxiosError('Network Error', 'ERR_NETWORK', config))
    expect(parsed.code).toBe('network_error')
    expect(parsed.status).toBeNull()
  })

  it('wraps unknown values', () => {
    expect(ApiError.from('boom').code).toBe('unknown_error')
  })
})
