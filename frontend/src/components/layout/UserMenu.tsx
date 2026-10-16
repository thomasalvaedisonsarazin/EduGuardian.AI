import { AnimatePresence, motion } from 'framer-motion'
import { LogOut, Moon, Sun } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '@/components/ui/Badge'
import { useAuth } from '@/hooks/useAuth'
import { useTheme } from '@/hooks/useTheme'
import { ROLE_LABELS } from '@/types/auth'

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const letters = parts.length > 1 ? `${parts[0][0]}${parts[parts.length - 1][0]}` : (parts[0]?.slice(0, 2) ?? '?')
  return letters.toUpperCase()
}

/** Avatar dropdown: user name/email, active-school role, theme toggle, sign out. */
export function UserMenu() {
  const [open, setOpen] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const { resolved, toggle } = useTheme()
  const { user, role, logout } = useAuth()

  useEffect(() => {
    if (!open) return
    const onPointer = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const signOut = async () => {
    setSigningOut(true)
    await logout()
    setOpen(false)
    navigate('/login', { replace: true })
  }

  const itemClass =
    'flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100 disabled:cursor-wait disabled:opacity-60 dark:text-slate-200 dark:hover:bg-slate-800'

  const name = user?.full_name ?? 'Account'

  return (
    <div ref={ref} className="relative">
      <motion.button
        type="button"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Open user menu"
        onClick={() => setOpen((o) => !o)}
        className="flex size-10 cursor-pointer items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-accent-500 text-sm font-semibold text-white shadow-md shadow-brand-600/20"
      >
        {initials(name)}
      </motion.button>
      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 z-50 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl dark:border-slate-700 dark:bg-slate-900"
          >
            <div className="border-b border-slate-100 px-3 pt-2 pb-3 dark:border-slate-800">
              <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">{name}</p>
              {user && <p className="truncate text-xs text-slate-500 dark:text-slate-400">{user.email}</p>}
              <div className="mt-2 flex flex-wrap gap-1.5">
                {role && <Badge tone="brand">{ROLE_LABELS[role]}</Badge>}
                {user?.is_superadmin && <Badge tone="accent">Superadmin</Badge>}
              </div>
            </div>
            <div className="pt-1.5">
              <button type="button" role="menuitem" onClick={toggle} className={itemClass}>
                {resolved === 'dark' ? <Sun aria-hidden className="size-4" /> : <Moon aria-hidden className="size-4" />}
                {resolved === 'dark' ? 'Light mode' : 'Dark mode'}
              </button>
              <button type="button" role="menuitem" onClick={() => void signOut()} disabled={signingOut} className={itemClass}>
                <LogOut aria-hidden className="size-4" />
                {signingOut ? 'Signing out…' : 'Sign out'}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
