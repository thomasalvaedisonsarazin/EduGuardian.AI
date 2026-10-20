import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  SESSION_CHANGED_EVENT,
  clearSession,
  getAccessToken,
  getActiveSchoolId,
  hasSession,
  setActiveSchoolId,
  setTokens,
} from './storage'

afterEach(() => {
  window.localStorage.clear()
  vi.restoreAllMocks()
})

describe('storage', () => {
  it('stores and clears tokens and active school', () => {
    setTokens({ access_token: 'a1' })
    setActiveSchoolId(7)
    expect(getAccessToken()).toBe('a1')
    expect(window.localStorage.getItem('eg.refresh_token')).toBeNull()
    expect(getActiveSchoolId()).toBe(7)
    expect(hasSession()).toBe(true)

    clearSession()
    expect(getAccessToken()).toBeNull()
    expect(window.localStorage.getItem('eg.access_token')).toBeNull()
    expect(getActiveSchoolId()).toBeNull()
  })

  it('returns null for a non-numeric school id', () => {
    window.localStorage.setItem('eg.active_school_id', 'abc')
    expect(getActiveSchoolId()).toBeNull()
  })

  it('emits a session-changed event', () => {
    const listener = vi.fn<() => void>()
    window.addEventListener(SESSION_CHANGED_EVENT, listener)
    setActiveSchoolId(1)
    window.removeEventListener(SESSION_CHANGED_EVENT, listener)
    expect(listener).toHaveBeenCalledTimes(1)
  })

  it('survives localStorage throwing', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(() => setTokens({ access_token: 'a' })).not.toThrow()
    expect(getAccessToken()).toBeNull()
  })
})

describe('refresh token', () => {
  it('is never kept in localStorage and legacy copies are removed', () => {
    window.localStorage.setItem('eg.refresh_token', 'old')
    setTokens({ access_token: 'a2' })
    expect(window.localStorage.getItem('eg.refresh_token')).toBeNull()
    expect(getAccessToken()).toBe('a2')
  })
})
