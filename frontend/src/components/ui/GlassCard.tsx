import { motion, type HTMLMotionProps } from 'framer-motion'
import { cn } from '@/lib/cn'

export interface GlassCardProps extends HTMLMotionProps<'div'> {
  /** Lift on hover (default true). Disable for large static containers such as tables. */
  hoverable?: boolean
  /** Inner padding preset (default "md"). */
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const paddings = { none: '', sm: 'p-4', md: 'p-6', lg: 'p-8' } as const

export function GlassCard({ hoverable = true, padding = 'md', className, children, ...props }: GlassCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      whileHover={hoverable ? { y: -3, boxShadow: '0 18px 40px -18px rgba(79, 70, 229, 0.35)' } : undefined}
      className={cn(
        'rounded-2xl border border-white/60 bg-white/70 shadow-sm shadow-slate-900/5 backdrop-blur-xl',
        'dark:border-white/10 dark:bg-slate-900/60 dark:shadow-black/20',
        paddings[padding],
        className,
      )}
      {...props}
    >
      {children}
    </motion.div>
  )
}
