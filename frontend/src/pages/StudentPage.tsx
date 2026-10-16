import { AlertTriangle, Award, Percent, TrendingUp, UserRound } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import {
  ChartCard,
  DeltaValue,
  PercentLineChart,
  ResultBadge,
  RiskReasonBadges,
  SeverityBadge,
  StatTile,
  fmtMarks,
  fmtPct,
  toNum,
  type ChartDatum,
} from '@/components/analytics'
import { EmptyState, GlassCard, PageSpinner, PageWrapper } from '@/components/ui'
import { parseId, useStudentTrend } from '@/hooks/useAnalytics'
import { getErrorMessage } from '@/services/api'
import type { StudentTrendPoint } from '@/types/analytics'

interface SubjectRow {
  subjectId: number
  name: string
}

function subjectRows(points: readonly StudentTrendPoint[]): SubjectRow[] {
  const seen = new Map<number, string>()
  for (const p of points) for (const s of p.result.subjects) if (!seen.has(s.subject_id)) seen.set(s.subject_id, s.subject_name)
  return [...seen.entries()].map(([subjectId, name]) => ({ subjectId, name })).sort((a, b) => a.name.localeCompare(b.name))
}

export default function StudentPage() {
  const params = useParams()
  const studentId = parseId(params.studentId)
  const { data, isLoading, error } = useStudentTrend(studentId)

  if (studentId === null || isLoading || error || !data) {
    return (
      <PageWrapper title="Student profile">
        {isLoading ? (
          <PageSpinner label="Loading student" />
        ) : (
          <GlassCard hoverable={false}>
            <EmptyState
              icon={AlertTriangle}
              title="Student not available"
              description={studentId === null ? 'Invalid student id.' : getErrorMessage(error)}
            />
          </GlassCard>
        )}
      </PageWrapper>
    )
  }

  const { student, points } = data
  const latest = points.at(-1)
  const chart: ChartDatum[] = points.map((p) => ({
    label: p.exam.name,
    student: toNum(p.result.percentage),
    section: toNum(p.section_mean_percentage),
  }))
  const subjects = subjectRows(points)

  return (
    <PageWrapper
      title={`${student.pseudo_id} · ${student.full_name}`}
      description={`Class ${student.class_label}`}
    >
      {!latest ? (
        <GlassCard hoverable={false}>
          <EmptyState icon={UserRound} title="No exam results yet" description="This student has no recorded marks." />
        </GlassCard>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatTile label="Latest overall" value={fmtPct(latest.result.percentage)} hint={latest.exam.name} icon={Percent} />
            <StatTile
              label="Rank in section"
              value={`${latest.result.rank_in_section} / ${latest.result.section_size}`}
              hint={`Class ${latest.result.class_label}`}
              icon={Award}
            />
            <StatTile
              label="Change"
              value={<DeltaValue value={latest.change?.delta ?? null} />}
              hint={latest.change ? 'vs previous exam' : 'No earlier exam'}
              icon={TrendingUp}
            />
            <StatTile
              label="Subjects failed"
              value={latest.result.failed_subjects.length}
              hint={`of ${latest.result.subjects.length}`}
              icon={AlertTriangle}
            />
          </div>

          {latest.at_risk && (
            <GlassCard hoverable={false} padding="sm" className="mt-6 border-l-4 border-l-rose-500">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Needs support after {latest.exam.name}</h2>
                <SeverityBadge severity={latest.at_risk.severity} />
                <RiskReasonBadges reasons={latest.at_risk.reasons} />
              </div>
              <ul className="mt-2 list-disc pl-5 text-sm text-slate-600 dark:text-slate-300">
                {latest.at_risk.reasons.map((r) => (
                  <li key={r.code}>{r.detail}</li>
                ))}
              </ul>
            </GlassCard>
          )}

          <ChartCard className="mt-6" title="Overall percentage across exams" description="Compared with the section mean">
            <PercentLineChart
              data={chart}
              series={[
                { key: 'student', name: student.pseudo_id },
                { key: 'section', name: `${student.class_label} mean` },
              ]}
              ariaLabel={`Line chart of ${student.pseudo_id}'s percentage across exams`}
            />
          </ChartCard>

          <section className="mt-6" aria-labelledby="subjects-heading">
            <h2 id="subjects-heading" className="mb-3 text-base font-semibold text-slate-900 dark:text-white">
              Subjects across exams
            </h2>
            <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white/80 dark:border-slate-800 dark:bg-slate-900/60">
              <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                <thead className="bg-slate-50/80 dark:bg-slate-900">
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left text-xs font-semibold text-slate-500 uppercase dark:text-slate-400">
                      Subject
                    </th>
                    {points.map((p) => (
                      <th key={p.exam.id} scope="col" className="px-3 py-2 text-left text-xs font-semibold text-slate-500 uppercase dark:text-slate-400">
                        {p.exam.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {subjects.map((row) => (
                    <tr key={row.subjectId}>
                      <th scope="row" className="px-3 py-2 text-left font-medium text-slate-800 dark:text-slate-100">
                        {row.name}
                      </th>
                      {points.map((p) => {
                        const s = p.result.subjects.find((x) => x.subject_id === row.subjectId)
                        const change = p.change?.subjects.find((x) => x.subject_id === row.subjectId)
                        return (
                          <td key={p.exam.id} className="px-3 py-2 text-slate-700 dark:text-slate-200">
                            {s ? (
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="tabular-nums">
                                  {s.is_absent ? '—' : fmtMarks(s.marks)}
                                  <span className="text-slate-400 dark:text-slate-500">/{fmtMarks(s.max_marks)}</span>
                                </span>
                                <ResultBadge passed={s.passed} isAbsent={s.is_absent} isMissing={s.is_missing} />
                                {change && <DeltaValue value={change.delta} />}
                              </div>
                            ) : (
                              <span className="text-slate-400">Not examined</span>
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                  <tr className="bg-slate-50/60 dark:bg-slate-900/40">
                    <th scope="row" className="px-3 py-2 text-left font-semibold text-slate-800 dark:text-slate-100">
                      Overall
                    </th>
                    {points.map((p) => (
                      <td key={p.exam.id} className="px-3 py-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold tabular-nums">{fmtPct(p.result.percentage, 2)}</span>
                          <ResultBadge passed={p.result.passed} />
                          {p.at_risk && <RiskReasonBadges reasons={p.at_risk.reasons} />}
                        </div>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <p className="mt-4 text-sm">
            <Link
              to={`/analytics/exams/${latest.exam.id}?class=${latest.result.class_section_id}`}
              className="font-medium text-brand-700 hover:underline dark:text-brand-300"
            >
              See {latest.result.class_label} results for {latest.exam.name}
            </Link>
          </p>
        </>
      )}
    </PageWrapper>
  )
}
