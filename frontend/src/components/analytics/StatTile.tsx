import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { GlassCard } from '@/components/ui'
import { cn } from '@/lib/cn'

export interface StatTileProps {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: LucideIcon
  className?: string
}

/** Headline number tile: label, one big value, optional context line. */
export function StatTile({ label, value, hint, icon: Icon, className }: StatTileProps) {
  return (
    <GlassCard padding="sm" className={cn('flex flex-col gap-1', className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">{label}</p>
        {Icon && <Icon aria-hidden className="size-4 text-brand-500 dark:text-brand-300" />}
      </div>
      <p className="text-2xl font-bold text-slate-900 tabular-nums dark:text-white">{value}</p>
      {hint && <p className="text-xs text-slate-500 dark:text-slate-400">{hint}</p>}
    </GlassCard>
  )
}
