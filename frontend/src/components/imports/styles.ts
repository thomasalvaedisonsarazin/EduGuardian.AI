import { cn } from '@/lib/cn'

/** Shared native <select> styling (matches the UI kit inputs). */
export const selectClass = cn(
  'h-9 rounded-xl border border-slate-200 bg-white/80 px-3 text-sm text-slate-900 outline-none',
  'focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15',
  'dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-100',
)
