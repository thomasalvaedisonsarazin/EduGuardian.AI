import { motion } from 'framer-motion'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface PageWrapperProps {
  title?: string
  description?: ReactNode
  /** Right-aligned header actions (buttons, filters). */
  actions?: ReactNode
  className?: string
  children?: ReactNode
}

/** Every page renders inside PageWrapper: fade-in transition + consistent header. */
export function PageWrapper({ title, description, actions, className, children }: PageWrapperProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={cn('mx-auto w-full max-w-7xl', className)}
    >
      {(title || actions) && (
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            {title && (
              <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl dark:text-white">{title}</h1>
            )}
            {description && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </motion.div>
  )
}
