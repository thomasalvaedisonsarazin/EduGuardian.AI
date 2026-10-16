import { Check } from 'lucide-react'
import { cn } from '@/lib/cn'
import { WIZARD_STEPS, type WizardStep } from './wizard'

export interface WizardStepsProps {
  current: WizardStep
  /** Highest step the user may jump to. */
  maxReachable: WizardStep
  onSelect: (step: WizardStep) => void
}

export function WizardSteps({ current, maxReachable, onSelect }: WizardStepsProps) {
  return (
    <ol className="flex flex-wrap items-center gap-2" aria-label="Import progress">
      {WIZARD_STEPS.map((label, i) => {
        const step = (i + 1) as WizardStep
        const done = step < current
        const active = step === current
        const reachable = step <= maxReachable
        return (
          <li key={label} className="flex items-center gap-2">
            <button
              type="button"
              disabled={!reachable}
              aria-current={active ? 'step' : undefined}
              onClick={() => onSelect(step)}
              className={cn(
                'flex cursor-pointer items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed',
                active && 'bg-brand-600 text-white',
                !active && done && 'bg-brand-50 text-brand-700 dark:bg-brand-950/50 dark:text-brand-300',
                !active && !done && 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
              )}
            >
              <span className="flex size-5 items-center justify-center rounded-full bg-white/30 text-xs">
                {done ? <Check aria-hidden className="size-3.5" /> : step}
              </span>
              {label}
            </button>
            {step < 4 && <span aria-hidden className="h-px w-6 bg-slate-300 dark:bg-slate-700" />}
          </li>
        )
      })}
    </ol>
  )
}
