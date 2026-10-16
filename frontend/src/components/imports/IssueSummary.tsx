import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui'
import type { IssueSummary as IssueSummaryData } from '@/types/imports'
import { ERROR_CODES, issueLabel } from './labels'

export interface IssueSummaryProps {
  summary: IssueSummaryData
  rowCount?: number
  /** Deterministic English summary from the Data Quality Agent. */
  text?: string
}

/** Severity badges + per-code counts for a validated import. */
export function IssueSummary({ summary, rowCount, text }: IssueSummaryProps) {
  const codes = Object.entries(summary.by_code).sort(([a, x], [b, y]) => y - x || a.localeCompare(b))
  const clean = summary.errors === 0 && summary.warnings === 0
  return (
    <section aria-label="Validation summary" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {rowCount !== undefined && <Badge tone="neutral">{rowCount} rows</Badge>}
        <Badge tone={summary.errors > 0 ? 'danger' : 'success'}>
          {summary.errors > 0 ? (
            <XCircle aria-hidden className="size-3.5" />
          ) : (
            <CheckCircle2 aria-hidden className="size-3.5" />
          )}
          {summary.errors} {summary.errors === 1 ? 'error' : 'errors'}
        </Badge>
        <Badge tone={summary.warnings > 0 ? 'warning' : 'neutral'}>
          <AlertTriangle aria-hidden className="size-3.5" />
          {summary.warnings} {summary.warnings === 1 ? 'warning' : 'warnings'}
        </Badge>
        {clean && <Badge tone="success">No issues found</Badge>}
      </div>
      {codes.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Issues by type">
          {codes.map(([code, count]) => (
            <li key={code}>
              <Badge tone={ERROR_CODES.has(code) ? 'danger' : 'warning'} dot>
                {issueLabel(code)}: {count}
              </Badge>
            </li>
          ))}
        </ul>
      )}
      {text && <p className="text-sm text-slate-600 dark:text-slate-300">{text}</p>}
    </section>
  )
}
