import { AlertTriangle, ArrowLeft, GraduationCap, Percent, Sigma, TrendingUp, Users } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  AtRiskTable,
  ChartCard,
  DeltaValue,
  GroupedBarChart,
  StatTile,
  StudentResultsTable,
  fmtPct,
  toNum,
  type ChartDatum,
  type ChartSeries,
} from '@/components/analytics'
import { DataTable, EmptyState, GlassCard, PageSpinner, PageWrapper, type DataTableColumn } from '@/components/ui'
import { parseId, useExamClass, useExamSummary } from '@/hooks/useAnalytics'
import { getErrorMessage } from '@/services/api'
import type { ClassSummary, ExamSummary, SubjectSummary } from '@/types/analytics'

/** Side-by-side series are limited to the 4 validated categorical colours. */
const MAX_SECTION_SERIES = 4

function subjectComparison(
  summary: ExamSummary,
  classId: number | null,
): { data: ChartDatum[]; series: ChartSeries[]; note?: string } {
  const sections = summary.class_summaries.filter((c) => c.class_section_id !== null)
  if (sections.length > 1 && sections.length <= MAX_SECTION_SERIES) {
    return {
      series: sections.map((c) => ({ key: `s${c.class_section_id}`, name: c.class_label })),
      data: summary.subject_summaries.map((s) => {
        const row: ChartDatum = { label: s.subject_name }
        for (const sec of s.sections) row[`s${sec.class_section_id}`] = toNum(sec.stats.pass_percentage)
        return row
      }),
    }
  }
  const selected = sections.find((c) => c.class_section_id === classId)
  const series: ChartSeries[] = [{ key: 'all', name: 'All classes' }]
  if (selected) series.push({ key: 'sel', name: selected.class_label })
  return {
    series,
    note:
      sections.length > MAX_SECTION_SERIES
        ? 'Too many sections to compare side by side - pick a class to compare it with the school.'
        : undefined,
    data: summary.subject_summaries.map((s) => ({
      label: s.subject_name,
      all: toNum(s.overall.pass_percentage),
      sel: selected
        ? toNum(s.sections.find((x) => x.class_section_id === selected.class_section_id)?.stats.pass_percentage)
        : null,
    })),
  }
}

export default function ExamAnalyticsPage() {
  const params = useParams()
  const examId = parseId(params.examId)
  const [search, setSearch] = useSearchParams()
  const classId = parseId(search.get('class') ?? undefined)

  const summaryQuery = useExamSummary(examId)
  const classQuery = useExamClass(examId, classId)

  const selectClass = (id: number | null) => {
    const next = new URLSearchParams(search)
    if (id === null) next.delete('class')
    else next.set('class', String(id))
    setSearch(next, { replace: true })
  }

  if (examId === null) {
    return (
      <PageWrapper title="Exam analytics">
        <GlassCard hoverable={false}>
          <EmptyState icon={AlertTriangle} title="Invalid exam" action={<Link to="/analytics">Back to exams</Link>} />
        </GlassCard>
      </PageWrapper>
    )
  }
  if (summaryQuery.isLoading) {
    return (
      <PageWrapper title="Exam analytics">
        <PageSpinner label="Analysing exam" />
      </PageWrapper>
    )
  }
  if (summaryQuery.error || !summaryQuery.data) {
    return (
      <PageWrapper title="Exam analytics">
        <GlassCard hoverable={false}>
          <EmptyState
            icon={AlertTriangle}
            title="Could not load this exam"
            description={getErrorMessage(summaryQuery.error)}
            action={
              <Link to="/analytics" className="text-sm font-medium text-brand-700 hover:underline dark:text-brand-300">
                Back to exams
              </Link>
            }
          />
        </GlassCard>
      </PageWrapper>
    )
  }

  const summary = summaryQuery.data
  const classData = classId !== null ? classQuery.data : undefined
  const current: ClassSummary =
    classId !== null
      ? (classData?.summary ??
        summary.class_summaries.find((c) => c.class_section_id === classId) ??
        summary.school_summary)
      : summary.school_summary
  const atRisk = classId !== null ? summary.at_risk.filter((a) => a.class_section_id === classId) : summary.at_risk
  const prev = summary.previous_exam
  const comparison = subjectComparison(summary, classId)
  const distribution: ChartDatum[] = current.distribution.map((b) => ({ label: `${b.label}%`, count: b.count }))

  const classColumns: DataTableColumn<ClassSummary>[] = [
    { id: 'class', header: 'Class', cell: (c) => <span className="font-medium">{c.class_label}</span> },
    { id: 'students', header: 'Students', align: 'right', cell: (c) => `${c.appeared_count}/${c.student_count}` },
    { id: 'pass', header: 'Pass %', align: 'right', cell: (c) => fmtPct(c.pass_percentage) },
    { id: 'mean', header: 'Mean', align: 'right', cell: (c) => fmtPct(c.mean_percentage) },
    { id: 'median', header: 'Median', align: 'right', cell: (c) => fmtPct(c.median_percentage) },
  ]
  const subjectColumns: DataTableColumn<SubjectSummary>[] = [
    { id: 'subject', header: 'Subject', cell: (s) => <span className="font-medium">{s.subject_name}</span> },
    { id: 'pass', header: 'Pass %', align: 'right', cell: (s) => fmtPct(s.overall.pass_percentage) },
    { id: 'mean', header: 'Mean', align: 'right', cell: (s) => fmtPct(s.overall.mean_percentage) },
    { id: 'absent', header: 'Absent', align: 'right', cell: (s) => s.overall.absent_count },
    {
      id: 'weakest',
      header: 'Weakest section',
      cell: (s) =>
        s.sections.length > 1
          ? s.sections
              .filter((x) => s.weakest_sections.includes(x.class_section_id))
              .map((x) => x.class_label)
              .join(', ')
          : '—',
    },
    ...(prev
      ? [
          {
            id: 'change',
            header: `vs ${prev.name}`,
            align: 'right' as const,
            cell: (s: SubjectSummary) => <DeltaValue value={s.mean_percentage_change} />,
          },
        ]
      : []),
  ]

  return (
    <PageWrapper
      title={summary.exam.name}
      description={
        <>
          Academic year {summary.exam.academic_year_label}
          {prev ? ` · Compared with ${prev.name}` : ' · No earlier exam to compare with'}
        </>
      }
      actions={
        <>
          <Link
            to="/analytics"
            className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-brand-700 dark:text-slate-300 dark:hover:text-brand-300"
          >
            <ArrowLeft aria-hidden className="size-4" />
            All exams
          </Link>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <span>Class</span>
            <select
              aria-label="Filter by class"
              value={classId ?? ''}
              onChange={(e) => selectClass(parseId(e.target.value))}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              <option value="">All classes</option>
              {summary.class_summaries.map((c) => (
                <option key={c.class_section_id ?? 'all'} value={c.class_section_id ?? ''}>
                  {c.class_label}
                </option>
              ))}
            </select>
          </label>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatTile label="Students" value={current.student_count} hint={`${current.appeared_count} appeared`} icon={Users} />
        <StatTile label="Pass rate" value={fmtPct(current.pass_percentage)} hint={`${current.pass_count} passed every subject`} icon={Percent} />
        <StatTile label="Mean" value={fmtPct(current.mean_percentage)} icon={TrendingUp} />
        <StatTile label="Median" value={fmtPct(current.median_percentage)} icon={Sigma} />
        <StatTile
          label="Need support"
          value={atRisk.length}
          hint={`${atRisk.filter((a) => a.severity === 'high').length} high priority`}
          icon={AlertTriangle}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <ChartCard title="Score distribution" description={`${current.class_label} · students who appeared`}>
          <GroupedBarChart
            data={distribution}
            series={[{ key: 'count', name: 'Students' }]}
            percent={false}
            height="md"
            ariaLabel="Bar chart of students per percentage band"
          />
        </ChartCard>
        <ChartCard title="Subject pass rate by section" description={comparison.note}>
          <GroupedBarChart
            data={comparison.data}
            series={comparison.series}
            height="md"
            ariaLabel="Bar chart comparing subject pass percentage across sections"
          />
        </ChartCard>
      </div>

      <section className="mt-6" aria-labelledby="subjects-heading">
        <h2 id="subjects-heading" className="mb-3 text-base font-semibold text-slate-900 dark:text-white">
          Subjects
        </h2>
        <DataTable columns={subjectColumns} rows={summary.subject_summaries} getRowId={(s) => s.subject_id} dense />
      </section>

      <section className="mt-6" aria-labelledby="risk-heading">
        <h2 id="risk-heading" className="mb-3 text-base font-semibold text-slate-900 dark:text-white">
          Students needing support
        </h2>
        <AtRiskTable students={atRisk} showDelta={prev !== null} dense />
      </section>

      <section className="mt-6" aria-labelledby="results-heading">
        <h2 id="results-heading" className="mb-3 text-base font-semibold text-slate-900 dark:text-white">
          {classId !== null ? `Results · ${current.class_label}` : 'Classes'}
        </h2>
        {classId === null ? (
          <>
            <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">Select a class to see every student's results.</p>
            <DataTable
              columns={classColumns}
              rows={summary.class_summaries}
              getRowId={(c) => c.class_section_id ?? 0}
              onRowClick={(c) => selectClass(c.class_section_id)}
              dense
              empty={<EmptyState icon={GraduationCap} title="No classes have marks for this exam" />}
            />
          </>
        ) : classQuery.error ? (
          <GlassCard hoverable={false}>
            <EmptyState icon={AlertTriangle} title="Could not load class results" description={getErrorMessage(classQuery.error)} />
          </GlassCard>
        ) : (
          <StudentResultsTable
            results={classData?.results ?? []}
            changes={classData?.changes ?? []}
            subjects={classData?.subjects ?? summary.subjects}
            previousExamName={prev?.name ?? null}
            loading={classQuery.isLoading}
          />
        )}
      </section>
    </PageWrapper>
  )
}
