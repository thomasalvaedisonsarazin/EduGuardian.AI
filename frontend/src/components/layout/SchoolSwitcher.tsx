import { motion } from 'framer-motion'
import { ChevronsUpDown, School as SchoolIcon } from 'lucide-react'
import { useActiveSchoolId } from '@/hooks/useSession'

/**
 * Placeholder school switcher. Module 1 (auth) will populate it from `GET /auth/me` memberships
 * and call `setActiveSchoolId()` from `@/lib/storage` on selection.
 */
export function SchoolSwitcher() {
  const activeSchoolId = useActiveSchoolId()
  return (
    <motion.button
      type="button"
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      aria-label="Switch school"
      className="inline-flex max-w-[14rem] cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-3 py-2 text-sm font-medium text-slate-700 hover:border-brand-300 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-200"
    >
      <SchoolIcon aria-hidden className="size-4 shrink-0 text-brand-600 dark:text-brand-400" />
      <span className="truncate">{activeSchoolId !== null ? `School #${activeSchoolId}` : 'Select school'}</span>
      <ChevronsUpDown aria-hidden className="size-4 shrink-0 text-slate-400" />
    </motion.button>
  )
}
