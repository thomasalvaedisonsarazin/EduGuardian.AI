import { AnimatePresence, motion } from 'framer-motion'
import { Check, ChevronsUpDown, School as SchoolIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/cn'
import { ROLE_LABELS } from '@/types/auth'

const chipClass =
  'inline-flex max-w-[14rem] items-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-3 py-2 text-sm font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-200'

/** Active-school picker in the top bar. A static chip when the user belongs to one school. */
export function SchoolSwitcher() {
  const { memberships, activeMembership, activeSchoolId, switchSchool } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

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

  const label = activeMembership?.school.name ?? (activeSchoolId !== null ? `School #${activeSchoolId}` : 'No school')

  if (memberships.length <= 1) {
    return (
      <div className={chipClass} title={label}>
        <SchoolIcon aria-hidden className="size-4 shrink-0 text-brand-600 dark:text-brand-400" />
        <span className="truncate">{label}</span>
      </div>
    )
  }

  return (
    <div ref={ref} className="relative">
      <motion.button
        type="button"
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Switch school (current: ${label})`}
        onClick={() => setOpen((o) => !o)}
        className={cn(chipClass, 'cursor-pointer hover:border-brand-300')}
      >
        <SchoolIcon aria-hidden className="size-4 shrink-0 text-brand-600 dark:text-brand-400" />
        <span className="truncate">{label}</span>
        <ChevronsUpDown aria-hidden className="size-4 shrink-0 text-slate-400" />
      </motion.button>
      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            aria-label="Your schools"
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 z-50 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl dark:border-slate-700 dark:bg-slate-900"
          >
            {memberships.map((m) => {
              const selected = m.school_id === activeSchoolId
              return (
                <button
                  key={m.id}
                  type="button"
                  role="menuitemradio"
                  aria-checked={selected}
                  onClick={() => {
                    switchSchool(m.school_id)
                    setOpen(false)
                  }}
                  className="flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{m.school.name}</span>
                    <span className="block text-xs text-slate-500 dark:text-slate-400">
                      {m.school.code} · {ROLE_LABELS[m.role]}
                    </span>
                  </span>
                  {selected && <Check aria-hidden className="size-4 shrink-0 text-brand-600 dark:text-brand-400" />}
                </button>
              )
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
