import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/cn'

export interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  /** Accessible label; also shown as text when `showLabel` is true. */
  label?: string
  showLabel?: boolean
  className?: string
}

const sizes = { sm: 'size-4', md: 'size-6', lg: 'size-10' } as const

export function Spinner({ size = 'md', label = 'Loading', showLabel = false, className }: SpinnerProps) {
  return (
    <output aria-live="polite" className={cn('inline-flex items-center gap-2 text-brand-600 dark:text-brand-400', className)}>
      <Loader2 aria-hidden className={cn('animate-spin', sizes[size])} />
      {showLabel ? (
        <span className="text-sm text-slate-600 dark:text-slate-300">{label}</span>
      ) : (
        <span className="sr-only">{label}</span>
      )}
    </output>
  )
}

/** Full-area centered spinner for route/page loading. */
export function PageSpinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner size="lg" label={label} showLabel />
    </div>
  )
}
