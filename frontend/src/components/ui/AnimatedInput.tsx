import { motion, type HTMLMotionProps } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import { useId, type Ref } from 'react'
import { cn } from '@/lib/cn'

export interface AnimatedInputProps extends HTMLMotionProps<'input'> {
  label?: string
  error?: string
  hint?: string
  icon?: LucideIcon
  ref?: Ref<HTMLInputElement>
  containerClassName?: string
}

/** Labelled text input with focus animation. React 19: `ref` is a regular prop (works with react-hook-form). */
export function AnimatedInput({
  label,
  error,
  hint,
  icon: Icon,
  id,
  className,
  containerClassName,
  ref,
  ...props
}: AnimatedInputProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined

  return (
    <div className={cn('space-y-1.5', containerClassName)}>
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-slate-700 dark:text-slate-200">
          {label}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <Icon aria-hidden className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-slate-400" />
        )}
        <motion.input
          ref={ref}
          id={inputId}
          whileFocus={{ scale: 1.005 }}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(
            'h-11 w-full rounded-xl border bg-white/80 px-4 text-sm text-slate-900 transition-colors outline-none placeholder:text-slate-400',
            'focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15',
            'dark:bg-slate-900/70 dark:text-slate-100 dark:placeholder:text-slate-500',
            error ? 'border-rose-400 dark:border-rose-500' : 'border-slate-200 dark:border-slate-700',
            Icon && 'pl-10',
            className,
          )}
          {...props}
        />
      </div>
      {error ? (
        <p id={`${inputId}-error`} className="text-sm text-rose-600 dark:text-rose-400">
          {error}
        </p>
      ) : hint ? (
        <p id={`${inputId}-hint`} className="text-xs text-slate-500 dark:text-slate-400">
          {hint}
        </p>
      ) : null}
    </div>
  )
}
