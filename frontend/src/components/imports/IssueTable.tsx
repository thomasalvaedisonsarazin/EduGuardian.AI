import { useMemo, useState } from 'react'
import { Badge, DataTable, EmptyState, type DataTableColumn } from '@/components/ui'
import type { IssueSeverity, ValidationIssue } from '@/types/imports'
import { issueLabel, SEVERITY_TONE } from './labels'
import { selectClass } from './styles'

type SeverityFilter = 'all' | IssueSeverity

const columns: DataTableColumn<ValidationIssue>[] = [
  {
    id: 'severity',
    header: 'Severity',
    cell: (i) => (
      <Badge tone={SEVERITY_TONE[i.severity]} dot>
        {i.severity}
      </Badge>
    ),
  },
  { id: 'code', header: 'Type', cell: (i) => issueLabel(i.code) },
  { id: 'row', header: 'Row', cell: (i) => i.row ?? '—', align: 'right' },
  { id: 'column', header: 'Column', cell: (i) => i.column ?? '—' },
  { id: 'message', header: 'Details', cell: (i) => i.message },
]

/** Issue list with severity and type filters. */
export function IssueTable({ issues }: { issues: readonly ValidationIssue[] }) {
  const [severity, setSeverity] = useState<SeverityFilter>('all')
  const [code, setCode] = useState('all')
  const codes = useMemo(() => [...new Set(issues.map((i) => i.code))].sort(), [issues])
  const filtered = useMemo(
    () => issues.filter((i) => (severity === 'all' || i.severity === severity) && (code === 'all' || i.code === code)),
    [issues, severity, code],
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
          Severity
          <select
            className={selectClass}
            value={severity}
            onChange={(e) => setSeverity(e.target.value as SeverityFilter)}
          >
            <option value="all">All</option>
            <option value="error">Errors</option>
            <option value="warning">Warnings</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
          Type
          <select className={selectClass} value={code} onChange={(e) => setCode(e.target.value)}>
            <option value="all">All types</option>
            {codes.map((c) => (
              <option key={c} value={c}>
                {issueLabel(c)}
              </option>
            ))}
          </select>
        </label>
        <span className="text-xs text-slate-500">
          Showing {filtered.length} of {issues.length}
        </span>
      </div>
      <DataTable
        dense
        caption="Validation issues"
        columns={columns}
        rows={filtered}
        getRowId={(i, idx) => `${i.code}-${i.row ?? 'x'}-${i.column ?? 'x'}-${idx}`}
        empty={<EmptyState title="No matching issues" />}
        className="max-h-96 overflow-y-auto"
      />
    </div>
  )
}
