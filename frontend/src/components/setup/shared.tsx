/** Small building blocks shared by the Academic Setup tabs. */
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Pencil, Trash2, X } from 'lucide-react'
import { useEffect, useId, useState, type FormEvent, type ReactNode } from 'react'
import { GradientButton } from '@/components/ui'
import { cn } from '@/lib/cn'
import { getErrorMessage } from '@/services/api'

// ---------------------------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------------------------
export interface ModalProps {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  wide?: boolean
}

export function Modal({ open, title, onClose, children, wide = false }: ModalProps) {
  const titleId = useId()
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.button
            type="button"
            aria-label="Close dialog"
            tabIndex={-1}
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 cursor-default bg-slate-900/50 backdrop-blur-sm"
          />
          <motion.dialog
            open
            aria-modal="true"
            aria-labelledby={titleId}
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.2 }}
            className={cn(
              'relative m-0 max-h-[90vh] w-full overflow-y-auto text-inherit rounded-2xl border border-white/60 bg-white p-6 shadow-2xl',
              'dark:border-white/10 dark:bg-slate-900',
              wide ? 'max-w-3xl' : 'max-w-lg',
            )}
          >
            <div className="mb-4 flex items-start justify-between gap-4">
              <h2 id={titleId} className="text-lg font-semibold text-slate-900 dark:text-white">
                {title}
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="rounded-full p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X aria-hidden className="size-5" />
              </button>
            </div>
            {children}
          </motion.dialog>
        </div>
      )}
    </AnimatePresence>
  )
}

// ---------------------------------------------------------------------------------------------
// Form helpers
// ---------------------------------------------------------------------------------------------
export interface SelectOption {
  value: string
  label: string
}

export interface SelectFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  options: readonly SelectOption[]
  placeholder?: string
  required?: boolean
  className?: string
}

export function SelectField({ label, value, onChange, options, placeholder, required, className }: SelectFieldProps) {
  const id = useId()
  return (
    <div className={cn('space-y-1.5', className)}>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700 dark:text-slate-200">
        {label}
      </label>
      <select
        id={id}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          'h-11 w-full rounded-xl border border-slate-200 bg-white/80 px-3 text-sm text-slate-900 outline-none',
          'focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15',
          'dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-100',
        )}
      >
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  )
}

export interface CheckboxFieldProps {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
}

export function CheckboxField({ label, checked, onChange }: CheckboxFieldProps) {
  const id = useId()
  return (
    <div className="flex items-center gap-2">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="size-4 rounded border-slate-300 accent-brand-600"
      />
      <label htmlFor={id} className="text-sm text-slate-700 dark:text-slate-200">
        {label}
      </label>
    </div>
  )
}

export function ErrorAlert({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300"
    >
      <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
      <span>{getErrorMessage(error)}</span>
    </div>
  )
}

export interface FormShellProps {
  onSubmit: () => void
  onCancel: () => void
  submitting: boolean
  error: unknown
  submitLabel?: string
  children: ReactNode
}

/** Form wrapper with error banner and Cancel/Save buttons. */
export function FormShell({ onSubmit, onCancel, submitting, error, submitLabel = 'Save', children }: FormShellProps) {
  const handle = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    onSubmit()
  }
  return (
    <form onSubmit={handle} className="space-y-4" noValidate>
      {children}
      <ErrorAlert error={error} />
      <div className="flex justify-end gap-2 pt-2">
        <GradientButton variant="ghost" onClick={onCancel}>
          Cancel
        </GradientButton>
        <GradientButton type="submit" loading={submitting}>
          {submitLabel}
        </GradientButton>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------------------------------------
// Row actions with inline delete confirmation
// ---------------------------------------------------------------------------------------------
export interface RowActionsProps {
  label: string
  onEdit?: () => void
  onDelete: () => Promise<unknown>
  extra?: ReactNode
}

export function RowActions({ label, onEdit, onDelete, extra }: RowActionsProps) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const confirm = async () => {
    setBusy(true)
    setError(null)
    try {
      await onDelete()
      setConfirming(false)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  if (confirming) {
    return (
      <div className="flex flex-col items-end gap-1">
        <div className="flex items-center justify-end gap-2">
          <span className="text-xs text-slate-600 dark:text-slate-300">Delete {label}?</span>
          <GradientButton size="sm" variant="danger" loading={busy} onClick={confirm}>
            Confirm
          </GradientButton>
          <GradientButton
            size="sm"
            variant="ghost"
            onClick={() => {
              setConfirming(false)
              setError(null)
            }}
          >
            Cancel
          </GradientButton>
        </div>
        {error !== null && (
          <p role="alert" className="max-w-xs text-right text-xs text-rose-600 dark:text-rose-400">
            {getErrorMessage(error)}
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="flex items-center justify-end gap-1">
      {extra}
      {onEdit && (
        <GradientButton size="sm" variant="ghost" icon={Pencil} onClick={onEdit} aria-label={`Edit ${label}`}>
          <span className="sr-only sm:not-sr-only">Edit</span>
        </GradientButton>
      )}
      <GradientButton
        size="sm"
        variant="ghost"
        icon={Trash2}
        onClick={() => setConfirming(true)}
        aria-label={`Delete ${label}`}
        className="text-rose-600 dark:text-rose-400"
      >
        <span className="sr-only sm:not-sr-only">Delete</span>
      </GradientButton>
    </div>
  )
}

export function Toolbar({ children }: { children: ReactNode }) {
  return <div className="mb-4 flex flex-wrap items-end justify-between gap-3">{children}</div>
}
