import { AlertTriangle, ArrowRight, Coins, FileText, Loader2, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { AgentRunDetail } from '@/types/agents'
import { LLM_MODE_LABELS, RUN_LABELS, RUN_TONES, formatCost } from './agentMeta'

export interface RunStatusBannerProps {
  run: AgentRunDetail
}

const linkClass =
  'inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-brand-500'

export function RunStatusBanner({ run }: RunStatusBannerProps) {
  const active = run.status === 'queued' || run.status === 'running'
  const drafts = run.plan_counts.draft ?? 0
  const mode = run.llm_mode ? (LLM_MODE_LABELS[run.llm_mode] ?? run.llm_mode) : null

  return (
    <section
      aria-label="Run status"
      aria-live="polite"
      className={cn(
        'rounded-2xl border p-5',
        run.status === 'failed'
          ? 'border-rose-200 bg-rose-50/70 dark:border-rose-900 dark:bg-rose-950/30'
          : 'border-brand-100 bg-gradient-to-r from-brand-50/80 to-accent-50/60 dark:border-slate-700 dark:from-slate-900 dark:to-slate-900',
      )}
    >
      <div className="flex flex-wrap items-center gap-3">
        {active && <Loader2 aria-hidden className="size-5 animate-spin text-brand-600" />}
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
          Run #{run.id}
          {run.exam_name ? ` · ${run.exam_name}` : ''}
        </h2>
        <Badge tone={RUN_TONES[run.status]} dot>
          {RUN_LABELS[run.status]}
        </Badge>
        {mode && (
          <Badge tone={run.llm_mode === 'llm' ? 'accent' : 'neutral'}>
            <Sparkles aria-hidden className="size-3" />
            {mode}
          </Badge>
        )}
        <span className="inline-flex items-center gap-1 text-sm text-slate-600 tabular-nums dark:text-slate-300">
          <Coins aria-hidden className="size-4" />
          {run.token_usage.toLocaleString()} tokens · {formatCost(run.cost_usd)}
        </span>
      </div>

      {run.error && (
        <p role="alert" className="mt-3 flex items-start gap-2 text-sm text-rose-700 dark:text-rose-300">
          <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
          {run.error}
        </p>
      )}

      {run.warnings.length > 0 && (
        <ul aria-label="Warnings" className="mt-3 space-y-1 text-sm text-amber-800 dark:text-amber-300">
          {run.warnings.map((w) => (
            <li key={w} className="flex items-start gap-2">
              <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
              {w}
            </li>
          ))}
        </ul>
      )}

      {!active && run.status !== 'failed' && (
        <div className="mt-4 flex flex-wrap gap-2">
          {drafts > 0 && (
            <Link
              to={`/interventions?run_id=${run.id}`}
              className={cn(linkClass, 'bg-gradient-to-r from-brand-600 to-accent-500 text-white shadow-md')}
            >
              Review {drafts} draft plan{drafts === 1 ? '' : 's'}
              <ArrowRight aria-hidden className="size-4" />
            </Link>
          )}
          {run.reports.length > 0 && (
            <Link
              to="/reports"
              className={cn(
                linkClass,
                'border border-brand-200 bg-white text-brand-700 hover:bg-brand-50 dark:border-brand-800 dark:bg-slate-900 dark:text-brand-200',
              )}
            >
              <FileText aria-hidden className="size-4" />
              {run.reports.length} report{run.reports.length === 1 ? '' : 's'} ({run.reports.map((r) => r.format.toUpperCase()).join(', ')})
            </Link>
          )}
        </div>
      )}
    </section>
  )
}
