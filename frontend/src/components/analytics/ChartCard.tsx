import type { ReactNode } from 'react'
import { GlassCard } from '@/components/ui'
import { cn } from '@/lib/cn'

export interface ChartCardProps {
  title: string
  description?: ReactNode
  actions?: ReactNode
  className?: string
  children: ReactNode
}

export function ChartCard({ title, description, actions, className, children }: ChartCardProps) {
  return (
    <GlassCard hoverable={false} padding="md" className={cn('flex flex-col gap-4', className)}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-white">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </GlassCard>
  )
}
