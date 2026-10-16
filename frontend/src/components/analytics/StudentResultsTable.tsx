import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { DataTable, type DataTableColumn } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { StudentChange, StudentResult, SubjectConfig } from '@/types/analytics'
import { DeltaValue, ResultBadge } from './Badges'
import { fmtMarks, fmtPct, toNum } from './format'

export type ResultSortKey = 'rank' | 'name' | 'percentage' | 'delta'
type SortDir = 'asc' | 'desc'

interface Row {
  result: StudentResult
  delta: number | null
}

export interface StudentResultsTableProps {
  results: readonly StudentResult[]
  changes: readonly StudentChange[]
  subjects: readonly SubjectConfig[]
  previousExamName?: string | null
  loading?: boolean
}

function compareRows(a: Row, b: Row, key: ResultSortKey): number {
  switch (key) {
    case 'rank':
      return a.result.rank_in_section - b.result.rank_in_section || a.result.pseudo_id.localeCompare(b.result.pseudo_id)
    case 'name':
      return a.result.full_name.localeCompare(b.result.full_name)
    case 'percentage':
      return (toNum(a.result.percentage) ?? 0) - (toNum(b.result.percentage) ?? 0)
    case 'delta':
      // Students without a comparison exam sort below everyone when descending.
      return (a.delta ?? Number.NEGATIVE_INFINITY) - (b.delta ?? Number.NEGATIVE_INFINITY)
  }
}

function sortResultRows(rows: readonly Row[], key: ResultSortKey, dir: SortDir): Row[] {
  const sorted = [...rows].sort((a, b) => compareRows(a, b, key))
  return dir === 'asc' ? sorted : sorted.reverse()
}

interface SortHeaderProps {
  label: string
  sortKey: ResultSortKey
  active: ResultSortKey
  dir: SortDir
  onSort: (key: ResultSortKey) => void
}

function SortHeader({ label, sortKey, active, dir, onSort }: SortHeaderProps) {
  const isActive = active === sortKey
  const Icon = !isActive ? ArrowUpDown : dir === 'asc' ? ArrowUp : ArrowDown
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      className={cn(
        'inline-flex cursor-pointer items-center gap-1 uppercase hover:text-brand-600 dark:hover:text-brand-300',
        isActive && 'text-brand-700 dark:text-brand-300',
      )}
      aria-label={`Sort by ${label}${isActive ? (dir === 'asc' ? ', ascending' : ', descending') : ''}`}
    >
      {label}
      <Icon aria-hidden className="size-3" />
    </button>
  )
}

/** Per-class results with sortable rank / name / percentage / change columns. */
export function StudentResultsTable({ results, changes, subjects, previousExamName, loading = false }: StudentResultsTableProps) {
  const [sortKey, setSortKey] = useState<ResultSortKey>('rank')
  const [dir, setDir] = useState<SortDir>('asc')

  const rows = useMemo(() => {
    const deltas = new Map(changes.map((c) => [c.student_id, toNum(c.delta)]))
    const base: Row[] = results.map((r) => ({ result: r, delta: deltas.get(r.student_id) ?? null }))
    return sortResultRows(base, sortKey, dir)
  }, [results, changes, sortKey, dir])

  const onSort = (key: ResultSortKey) => {
    if (key === sortKey) {
      setDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setDir(key === 'percentage' || key === 'delta' ? 'desc' : 'asc')
    }
  }
  const header = (label: string, key: ResultSortKey) => (
    <SortHeader label={label} sortKey={key} active={sortKey} dir={dir} onSort={onSort} />
  )

  const columns: DataTableColumn<Row>[] = [
    { id: 'rank', header: header('Rank', 'rank'), align: 'right', cell: (r) => <span className="tabular-nums">{r.result.rank_in_section}</span> },
    {
      id: 'name',
      header: header('Student', 'name'),
      cell: ({ result }) => (
        <Link to={`/students/${result.student_id}`} className="font-medium text-brand-700 hover:underline dark:text-brand-300">
          {result.pseudo_id}
          <span className="ml-2 font-normal text-slate-500 dark:text-slate-400">{result.full_name}</span>
        </Link>
      ),
    },
    ...subjects.map<DataTableColumn<Row>>((cfg) => ({
      id: `subject-${cfg.subject_id}`,
      header: cfg.name,
      align: 'right',
      cell: ({ result }) => {
        const s = result.subjects.find((x) => x.subject_id === cfg.subject_id)
        if (!s) return '—'
        if (s.is_absent) return <span className="text-amber-700 dark:text-amber-400">Abs</span>
        return (
          <span
            className={cn('tabular-nums', !s.passed && 'font-semibold text-rose-700 dark:text-rose-400')}
            title={s.passed ? undefined : `Below pass mark (${fmtMarks(s.pass_marks)})`}
          >
            {fmtMarks(s.marks)}
            {!s.passed && <span className="sr-only"> (fail)</span>}
          </span>
        )
      },
    })),
    {
      id: 'total',
      header: 'Total',
      align: 'right',
      cell: ({ result }) => (
        <span className="tabular-nums">
          {fmtMarks(result.total)}
          <span className="text-slate-400 dark:text-slate-500">/{fmtMarks(result.max_total)}</span>
        </span>
      ),
    },
    { id: 'pct', header: header('%', 'percentage'), align: 'right', cell: ({ result }) => <span className="font-semibold tabular-nums">{fmtPct(result.percentage, 2)}</span> },
    {
      id: 'result',
      header: 'Result',
      cell: ({ result }) => <ResultBadge passed={result.passed} isMissing={!result.appeared} />,
    },
    ...(previousExamName
      ? [
          {
            id: 'delta',
            header: header(`vs ${previousExamName}`, 'delta'),
            align: 'right' as const,
            cell: (r: Row) => <DeltaValue value={r.delta === null ? null : String(r.delta)} />,
          },
        ]
      : []),
  ]

  return (
    <DataTable
      columns={columns}
      rows={rows}
      getRowId={(r) => r.result.student_id}
      loading={loading}
      dense
      caption="Student results"
    />
  )
}
