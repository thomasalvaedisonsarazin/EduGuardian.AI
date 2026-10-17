import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, ChevronDown, Circle, Loader2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { AgentRunStatus, AgentStepStatus } from '@/types'
import type { AgentStepDetail } from '@/types/agents'
import { AGENT_ORDER, STEP_LABELS, STEP_TONES, agentMeta, formatDuration, stepHighlights } from './agentMeta'
import { KeyValueList } from './KeyValueList'

export interface AgentStepTimelineProps {
  steps: readonly AgentStepDetail[]
  runStatus: AgentRunStatus
}

interface TimelineEntry {
  key: string
  agentName: string
  status: AgentStepStatus
  step: AgentStepDetail | null
}

/** Real steps in order, followed by placeholders for agents that have not started yet. */
function buildEntries(steps: readonly AgentStepDetail[], runStatus: AgentRunStatus): TimelineEntry[] {
  const entries: TimelineEntry[] = steps.map((step) => ({
    key: `step-${step.id}`,
    agentName: step.agent_name,
    status: step.status,
    step,
  }))
  const seen = new Set(steps.map((s) => s.agent_name))
  const ended = runStatus === 'failed'
  for (const name of AGENT_ORDER) {
    if (!seen.has(name)) {
      entries.push({ key: `pending-${name}`, agentName: name, status: ended ? 'skipped' : 'pending', step: null })
    }
  }
  return entries
}

const statusRing: Record<AgentStepStatus, string> = {
  pending: 'border-slate-200 bg-white text-slate-400 dark:border-slate-700 dark:bg-slate-900',
  running: 'border-sky-300 bg-sky-50 text-sky-600 dark:border-sky-700 dark:bg-sky-950',
  done: 'border-emerald-300 bg-emerald-50 text-emerald-600 dark:border-emerald-700 dark:bg-emerald-950',
  failed: 'border-rose-300 bg-rose-50 text-rose-600 dark:border-rose-700 dark:bg-rose-950',
  skipped: 'border-slate-200 bg-slate-50 text-slate-300 dark:border-slate-700 dark:bg-slate-900',
}

function StatusGlyph({ status }: { status: AgentStepStatus }) {
  if (status === 'running') return <Loader2 aria-hidden className="size-3.5 animate-spin" />
  if (status === 'done') return <CheckCircle2 aria-hidden className="size-3.5" />
  if (status === 'failed') return <XCircle aria-hidden className="size-3.5" />
  return <Circle aria-hidden className="size-3.5" />
}

function TimelineItem({ entry, isLast }: { entry: TimelineEntry; isLast: boolean }) {
  const [open, setOpen] = useState(false)
  const meta = agentMeta(entry.agentName)
  const Icon = meta.icon
  const step = entry.step
  const highlights = stepHighlights(entry.agentName, step?.output_summary ?? null)
  const hasDetails = Boolean(step && (step.output_summary || step.input_summary))
  const detailsId = `step-details-${entry.key}`

  return (
    <motion.li
      layout
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
      className="relative flex gap-4 pb-6 last:pb-0"
      aria-label={`${meta.label}: ${STEP_LABELS[entry.status]}`}
    >
      {!isLast && (
        <span
          aria-hidden
          className={cn(
            'absolute top-11 left-[1.3rem] h-[calc(100%-2.75rem)] w-0.5',
            entry.status === 'done' ? 'bg-emerald-300 dark:bg-emerald-800' : 'bg-slate-200 dark:bg-slate-700',
          )}
        />
      )}
      <div className="relative shrink-0">
        {entry.status === 'running' && (
          <motion.span
            aria-hidden
            className="absolute inset-0 rounded-full bg-sky-400/30"
            animate={{ scale: [1, 1.5, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ duration: 1.6, repeat: Infinity }}
          />
        )}
        <div className={cn('relative flex size-11 items-center justify-center rounded-full border-2', statusRing[entry.status])}>
          <Icon aria-hidden className="size-5" />
        </div>
      </div>

      <div className="min-w-0 flex-1 pt-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-semibold text-slate-900 dark:text-slate-100">{meta.label}</h3>
          <Badge tone={STEP_TONES[entry.status]}>
            <StatusGlyph status={entry.status} />
            {STEP_LABELS[entry.status]}
          </Badge>
          {step && step.duration_ms !== null && (
            <span className="text-xs text-slate-500 tabular-nums dark:text-slate-400">{formatDuration(step.duration_ms)}</span>
          )}
        </div>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{meta.description}</p>

        {highlights.length > 0 && (
          <ul aria-label={`${meta.label} results`} className="mt-2 flex flex-wrap gap-2">
            {highlights.map((h) => (
              <li
                key={h.label}
                className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300"
              >
                {h.label}: <span className="font-semibold text-slate-900 tabular-nums dark:text-white">{h.value}</span>
              </li>
            ))}
          </ul>
        )}

        {step?.error && (
          <p role="alert" className="mt-2 flex items-start gap-1.5 text-sm text-rose-700 dark:text-rose-400">
            <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
            {step.error}
          </p>
        )}

        {hasDetails && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls={detailsId}
            className="mt-2 inline-flex cursor-pointer items-center gap-1 text-xs font-medium text-brand-700 hover:underline dark:text-brand-300"
          >
            <ChevronDown aria-hidden className={cn('size-3.5 transition-transform', open && 'rotate-180')} />
            {open ? 'Hide details' : 'Show details'}
          </button>
        )}
        <AnimatePresence initial={false}>
          {open && step && (
            <motion.div
              id={detailsId}
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="mt-3 space-y-3 rounded-xl border border-slate-200 bg-white/70 p-3 dark:border-slate-700 dark:bg-slate-900/60">
                {step.output_summary && (
                  <section>
                    <h4 className="mb-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">Output</h4>
                    <KeyValueList data={step.output_summary} />
                  </section>
                )}
                {step.input_summary && (
                  <section>
                    <h4 className="mb-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">Input</h4>
                    <KeyValueList data={step.input_summary} />
                  </section>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.li>
  )
}

/** Vertical, animated timeline of the orchestrator's agent steps. */
export function AgentStepTimeline({ steps, runStatus }: AgentStepTimelineProps) {
  const entries = buildEntries(steps, runStatus)
  return (
    <ol aria-label="Agent steps" className="relative">
      {entries.map((entry, i) => (
        <TimelineItem key={entry.key} entry={entry} isLast={i === entries.length - 1} />
      ))}
    </ol>
  )
}
