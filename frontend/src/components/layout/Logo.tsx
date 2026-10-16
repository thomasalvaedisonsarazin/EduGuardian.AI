import { ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/cn'

export function Logo({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <span className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-600 to-accent-500 text-white shadow-md shadow-brand-600/30">
        <ShieldCheck aria-hidden className="size-5" />
      </span>
      {!compact && (
        <span className="text-base leading-tight font-bold tracking-tight text-slate-900 dark:text-white">
          EduGuardian <span className="bg-gradient-to-r from-brand-600 to-accent-500 bg-clip-text text-transparent">AI</span>
        </span>
      )}
    </span>
  )
}
