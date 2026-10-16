import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { Badge } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { DecimalString, RiskReason, RiskSeverity } from '@/types/analytics'
import { fmtDelta, toNum } from './format'
import { RISK_LABELS, RISK_TONES, SEVERITY_TONES } from './risk'

export interface RiskReasonBadgesProps {
  reasons: readonly RiskReason[]
  className?: string
}

/** One badge per at-risk reason; the full detail is available as the badge title. */
export function RiskReasonBadges({ reasons, className }: RiskReasonBadgesProps) {
  if (reasons.length === 0) return null
  return (
    <ul aria-label="Risk reasons" className={cn('flex flex-wrap gap-1.5', className)}>
      {reasons.map((reason) => (
        <li key={reason.code} title={reason.detail}>
          <Badge tone={RISK_TONES[reason.code]}>{RISK_LABELS[reason.code]}</Badge>
        </li>
      ))}
    </ul>
  )
}

export function SeverityBadge({ severity }: { severity: RiskSeverity }) {
  return (
    <Badge tone={SEVERITY_TONES[severity]} dot>
      {severity === 'high' ? 'High' : 'Medium'}
    </Badge>
  )
}

export interface ResultBadgeProps {
  passed: boolean
  isAbsent?: boolean
  isMissing?: boolean
}

export function ResultBadge({ passed, isAbsent = false, isMissing = false }: ResultBadgeProps) {
  if (isAbsent) return <Badge tone="warning">Absent</Badge>
  if (isMissing) return <Badge tone="neutral">No mark</Badge>
  return passed ? <Badge tone="success">Pass</Badge> : <Badge tone="danger">Fail</Badge>
}

/** Signed change in percentage points with an arrow icon (never colour alone). */
export function DeltaValue({ value }: { value: DecimalString | null | undefined }) {
  const n = toNum(value)
  if (n === null) return <span className="text-slate-400 dark:text-slate-500">—</span>
  const Icon = n > 0 ? ArrowUpRight : n < 0 ? ArrowDownRight : Minus
  return (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 tabular-nums',
        n > 0 && 'text-emerald-700 dark:text-emerald-400',
        n < 0 && 'text-rose-700 dark:text-rose-400',
        n === 0 && 'text-slate-500 dark:text-slate-400',
      )}
    >
      <Icon aria-hidden className="size-3.5" />
      {fmtDelta(n)}
    </span>
  )
}
