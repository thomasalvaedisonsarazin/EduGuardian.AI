import { ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { DataTable, EmptyState, type DataTableColumn } from '@/components/ui'
import type { AtRiskStudent } from '@/types/analytics'
import { DeltaValue, RiskReasonBadges, SeverityBadge } from './Badges'
import { fmtPct } from './format'

export interface AtRiskTableProps {
  students: readonly AtRiskStudent[]
  loading?: boolean
  /** Show the "change vs previous exam" column (hidden when there is no comparison exam). */
  showDelta?: boolean
  dense?: boolean
}

export function AtRiskTable({ students, loading = false, showDelta = true, dense = false }: AtRiskTableProps) {
  const columns: DataTableColumn<AtRiskStudent>[] = [
    {
      id: 'student',
      header: 'Student',
      cell: (s) => (
        <Link
          to={`/students/${s.student_id}`}
          className="font-medium text-brand-700 hover:underline dark:text-brand-300"
        >
          {s.pseudo_id}
          <span className="ml-2 font-normal text-slate-500 dark:text-slate-400">{s.full_name}</span>
        </Link>
      ),
    },
    { id: 'class', header: 'Class', cell: (s) => s.class_label },
    { id: 'severity', header: 'Priority', cell: (s) => <SeverityBadge severity={s.severity} /> },
    { id: 'pct', header: 'Overall', align: 'right', cell: (s) => <span className="tabular-nums">{fmtPct(s.percentage)}</span> },
    ...(showDelta
      ? [{ id: 'delta', header: 'Change', align: 'right' as const, cell: (s: AtRiskStudent) => <DeltaValue value={s.delta} /> }]
      : []),
    {
      id: 'reasons',
      header: 'Why flagged',
      cell: (s) => (
        <div className="flex flex-col gap-1">
          <RiskReasonBadges reasons={s.reasons} />
          <span className="text-xs text-slate-500 dark:text-slate-400">{s.reasons.map((r) => r.detail).join(' · ')}</span>
        </div>
      ),
    },
  ]
  return (
    <DataTable
      columns={columns}
      rows={students}
      getRowId={(s) => s.student_id}
      loading={loading}
      dense={dense}
      caption="Students needing support"
      empty={<EmptyState icon={ShieldCheck} title="No students flagged" description="Nobody meets the at-risk rule for this selection." />}
    />
  )
}
