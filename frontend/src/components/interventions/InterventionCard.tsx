import { CalendarClock, Check, CheckCheck, Pencil, PlayCircle, Sparkles, X } from 'lucide-react'
import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { RiskReasonBadges, SeverityBadge, fmtDelta, fmtMarks, fmtPct } from '@/components/analytics'
import { Badge, GlassCard, GradientButton } from '@/components/ui'
import type { InterventionItem, InterventionUpdateInput } from '@/types/interventions'
import {
  STATUS_LABELS,
  STATUS_TONES,
  draftMeta,
  dropInfo,
  failedSubjects,
  overallPercentage,
  parseReasons,
  rejectionReason,
} from './evidence'
import { PlanEditForm } from './PlanEditForm'

export interface InterventionCardProps {
  item: InterventionItem
  busy?: boolean
  onApprove: (id: number) => void
  onReject: (id: number, reason?: string) => void
  onSave: (id: number, input: InterventionUpdateInput) => void
  onStatus: (id: number, status: 'in_progress' | 'completed') => void
}

const OWNER_TONES = { teacher: 'brand', student: 'accent', parent: 'info' } as const

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

/** One plan in the review queue: who, why (evidence), what (plan) and the review actions. */
export function InterventionCard({ item, busy = false, onApprove, onReject, onSave, onStatus }: InterventionCardProps) {
  const reasonId = useId()
  const [editing, setEditing] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')

  const reasons = parseReasons(item.evidence)
  const failed = failedSubjects(item.evidence)
  const drop = dropInfo(item.evidence)
  const draft = draftMeta(item.evidence)
  const overall = overallPercentage(item.evidence)
  const rejected = rejectionReason(item.evidence)
  const isDraft = item.status === 'draft'
  const severity = item.severity === 'high' || item.severity === 'medium' ? item.severity : null

  return (
    <GlassCard hoverable={false} padding="none" className="overflow-hidden" aria-label={`Plan for ${item.student.full_name}`}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 p-5 dark:border-slate-800">
        <div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">
            <Link to={`/students/${item.student.id}`} className="hover:underline">
              {item.student.full_name}
            </Link>
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {item.student.pseudo_id} · Class {item.student.class_label}
            {item.exam_name ? ` · ${item.exam_name}` : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {severity && <SeverityBadge severity={severity} />}
          <Badge tone={STATUS_TONES[item.status]}>{STATUS_LABELS[item.status]}</Badge>
          {draft.mode && (
            <Badge tone={draft.mode === 'llm' ? 'accent' : 'neutral'}>
              <Sparkles aria-hidden className="size-3" />
              {draft.mode === 'llm' ? 'AI draft' : 'Template draft'}
            </Badge>
          )}
        </div>
      </header>

      <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,18rem)_1fr]">
        <section aria-label="Evidence" className="space-y-3 text-sm">
          <h4 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">Why this student</h4>
          <RiskReasonBadges reasons={reasons} />
          {overall && (
            <p className="text-slate-700 dark:text-slate-300">
              Overall: <span className="font-semibold tabular-nums">{fmtPct(overall)}</span>
            </p>
          )}
          {failed.length > 0 && (
            <ul aria-label="Subjects below the pass mark" className="space-y-1">
              {failed.map((s) => (
                <li key={s.name} className="flex justify-between gap-2 text-slate-700 dark:text-slate-300">
                  <span>{s.name}</span>
                  <span className="tabular-nums">
                    {s.absent ? 'Absent' : `${fmtMarks(s.marks)}/${fmtMarks(s.maxMarks)}`}
                    <span className="text-slate-400"> (pass {fmtMarks(s.passMarks)})</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {drop && (
            <p className="text-slate-700 dark:text-slate-300">
              Change: <span className="font-semibold tabular-nums">{fmtDelta(drop.delta)}</span>{' '}
              <span className="text-slate-400">
                ({fmtPct(drop.previous)} → {fmtPct(drop.current)})
              </span>
            </p>
          )}
        </section>

        <section aria-label="Plan" className="min-w-0 space-y-3">
          {editing ? (
            <PlanEditForm
              item={item}
              saving={busy}
              onCancel={() => setEditing(false)}
              onSave={(input) => {
                onSave(item.id, input)
                setEditing(false)
              }}
            />
          ) : (
            <>
              {draft.summary && <p className="font-medium text-slate-800 dark:text-slate-100">{draft.summary}</p>}
              {item.activities.length > 0 && (
                <ul aria-label="Activities" className="space-y-2">
                  {item.activities.map((a, i) => (
                    <li key={`${a.title}-${i}`} className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-slate-900 dark:text-white">{a.title}</span>
                        <Badge tone={OWNER_TONES[a.owner]}>{a.owner}</Badge>
                        <span className="text-xs text-slate-500 dark:text-slate-400">{a.frequency}</span>
                      </div>
                      <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{a.description}</p>
                    </li>
                  ))}
                </ul>
              )}
              <details className="text-sm">
                <summary className="cursor-pointer text-brand-700 dark:text-brand-300">Full plan text</summary>
                <p className="mt-2 whitespace-pre-line text-slate-700 dark:text-slate-300">{item.plan_text}</p>
              </details>
              <p className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                <CalendarClock aria-hidden className="size-3.5" />
                Reassess on {fmtDate(item.reassess_on)}
                {item.approved_by_email && item.approved_at && (
                  <span>
                    {' '}
                    · Approved by {item.approved_by_email} on {fmtDate(item.approved_at)}
                  </span>
                )}
              </p>
              {rejected && <p className="text-sm text-slate-500">Rejection reason: {rejected}</p>}
            </>
          )}
        </section>
      </div>

      {item.can_review && !editing && item.status !== 'completed' && item.status !== 'rejected' && (
        <footer className="space-y-3 border-t border-slate-100 bg-slate-50/60 p-4 dark:border-slate-800 dark:bg-slate-900/40">
          {rejecting ? (
            <div className="space-y-2">
              <label htmlFor={reasonId} className="text-sm font-medium text-slate-700 dark:text-slate-200">
                Reason for rejecting (optional)
              </label>
              <textarea
                id={reasonId}
                rows={2}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
              />
              <div className="flex gap-2">
                <GradientButton
                  variant="danger"
                  size="sm"
                  icon={X}
                  loading={busy}
                  onClick={() => {
                    onReject(item.id, reason.trim() || undefined)
                    setRejecting(false)
                  }}
                >
                  Confirm reject
                </GradientButton>
                <GradientButton variant="ghost" size="sm" onClick={() => setRejecting(false)}>
                  Cancel
                </GradientButton>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {isDraft && (
                <>
                  <GradientButton size="sm" icon={Check} loading={busy} onClick={() => onApprove(item.id)}>
                    Approve
                  </GradientButton>
                  <GradientButton variant="secondary" size="sm" icon={Pencil} disabled={busy} onClick={() => setEditing(true)}>
                    Edit
                  </GradientButton>
                  <GradientButton variant="ghost" size="sm" icon={X} disabled={busy} onClick={() => setRejecting(true)}>
                    Reject
                  </GradientButton>
                </>
              )}
              {item.status === 'approved' && (
                <GradientButton size="sm" icon={PlayCircle} loading={busy} onClick={() => onStatus(item.id, 'in_progress')}>
                  Start intervention
                </GradientButton>
              )}
              {item.status === 'in_progress' && (
                <GradientButton size="sm" icon={CheckCheck} loading={busy} onClick={() => onStatus(item.id, 'completed')}>
                  Mark completed
                </GradientButton>
              )}
            </div>
          )}
        </footer>
      )}
    </GlassCard>
  )
}
