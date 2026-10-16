import { motion, type HTMLMotionProps } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { Spinner } from './Spinner'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface GradientButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: LucideIcon
  iconRight?: LucideIcon
  fullWidth?: boolean
  children?: ReactNode
}

const variants: Record<ButtonVariant, string> = {
  primary:
    'text-white bg-gradient-to-r from-brand-600 to-accent-500 shadow-md shadow-brand-600/25 hover:shadow-lg hover:shadow-brand-600/30',
  secondary:
    'text-brand-700 bg-white border border-brand-200 hover:bg-brand-50 dark:bg-slate-900 dark:text-brand-200 dark:border-brand-800 dark:hover:bg-slate-800',
  ghost: 'text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800',
  danger: 'text-white bg-gradient-to-r from-rose-600 to-red-500 shadow-md shadow-rose-600/25 hover:shadow-lg',
}

const sizes: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm gap-1.5',
  md: 'h-10 px-5 text-sm gap-2',
  lg: 'h-12 px-6 text-base gap-2',
}

export function GradientButton({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon: Icon,
  iconRight: IconRight,
  fullWidth = false,
  disabled,
  className,
  children,
  type = 'button',
  ...props
}: GradientButtonProps) {
  const isDisabled = Boolean(disabled) || loading
  return (
    <motion.button
      type={type}
      whileHover={isDisabled ? undefined : { scale: 1.02, y: -1 }}
      whileTap={isDisabled ? undefined : { scale: 0.97 }}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex cursor-pointer items-center justify-center rounded-full font-semibold transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-60',
        variants[variant],
        sizes[size],
        fullWidth && 'w-full',
        className,
      )}
      {...props}
    >
      {loading ? <Spinner size="sm" className="text-current" /> : Icon && <Icon aria-hidden className="size-4 shrink-0" />}
      {children}
      {IconRight && !loading && <IconRight aria-hidden className="size-4 shrink-0" />}
    </motion.button>
  )
}
