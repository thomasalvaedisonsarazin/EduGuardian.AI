import { useSyncExternalStore } from 'react'
import { SESSION_CHANGED_EVENT, getAccessToken, getActiveSchoolId } from '@/lib/storage'
import type { ID } from '@/types'

function subscribe(callback: () => void): () => void {
  window.addEventListener(SESSION_CHANGED_EVENT, callback)
  window.addEventListener('storage', callback)
  return () => {
    window.removeEventListener(SESSION_CHANGED_EVENT, callback)
    window.removeEventListener('storage', callback)
  }
}

/** Reactive view of the stored session (re-renders when tokens or active school change). */
export function useActiveSchoolId(): ID | null {
  return useSyncExternalStore(subscribe, getActiveSchoolId, () => null)
}

export function useHasSession(): boolean {
  return useSyncExternalStore(subscribe, () => getAccessToken() !== null, () => false)
}
