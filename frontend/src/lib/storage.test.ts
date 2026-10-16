import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  SESSION_CHANGED_EVENT,
  clearSession,
  getAccessToken,
  getActiveSchoolId,
  getRefreshToken,
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
    setTokens({ access_token: 'a1', refresh_token: 'r1' })
    setActiveSchoolId(7)
    expect(getAccessToken()).toBe('a1')
    expect(getRefreshToken()).toBe('r1')
    expect(getActiveSchoolId()).toBe(7)
    expect(hasSession()).toBe(true)

    clearSession()
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
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
    expect(() => setTokens({ access_token: 'a', refresh_token: 'r' })).not.toThrow()
    expect(getAccessToken()).toBeNull()
  })
})
