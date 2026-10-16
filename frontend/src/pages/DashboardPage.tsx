import { AlertTriangle, ArrowRight, GraduationCap, LayoutDashboard, Percent, TrendingUp, Upload } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  AtRiskTable,
  ChartCard,
  GroupedBarChart,
  PercentLineChart,
  StatTile,
  fmtPct,
  toNum,
  type ChartDatum,
} from '@/components/analytics'
import { EmptyState, GlassCard, PageSpinner, PageWrapper } from '@/components/ui'
import { useDashboardOverview } from '@/hooks/useAnalytics'
import { getErrorMessage } from '@/services/api'

const linkButton =
  'inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-colors'

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboardOverview()

  const description = 'School-wide performance overview and students needing support.'

  if (isLoading) {
    return (
      <PageWrapper title="Dashboard" description={description}>
        <PageSpinner label="Loading overview" />
      </PageWrapper>
    )
  }

  if (error || !data) {
    return (
      <PageWrapper title="Dashboard" description={description}>
        <GlassCard hoverable={false}>
          <EmptyState icon={AlertTriangle} title="Could not load the overview" description={getErrorMessage(error)} />
        </GlassCard>
      </PageWrapper>
    )
  }

  if (!data.latest_exam || !data.summary) {
    return (
      <PageWrapper title="Dashboard" description={description}>
        <GlassCard hoverable={false}>
          <EmptyState
            icon={LayoutDashboard}
            title="No results to analyse yet"
            description="Set up classes, subjects and exams, then import marks. Analytics appear here as soon as marks are recorded."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Link to="/setup" className={`${linkButton} bg-brand-600 text-white hover:bg-brand-700`}>
                  Go to setup
                </Link>
                <Link
                  to="/imports/new"
                  className={`${linkButton} border border-brand-200 text-brand-700 hover:bg-brand-50 dark:border-brand-800 dark:text-brand-200 dark:hover:bg-slate-800`}
                >
                  <Upload aria-hidden className="size-4" />
                  Import marks
                </Link>
              </div>
            }
          />
        </GlassCard>
      </PageWrapper>
    )
  }

  const exam = data.latest_exam
  const summary = data.summary
  const trend: ChartDatum[] = data.trend.map((t) => ({
    label: t.exam.name,
    pass: toNum(t.pass_percentage),
    mean: toNum(t.mean_percentage),
  }))
  const subjectBars: ChartDatum[] = data.subjects.map((s) => ({
    label: s.subject_name,
    pass: toNum(s.overall.pass_percentage),
  }))

  return (
    <PageWrapper
      title="Dashboard"
      description={`Latest results: ${exam.name} (${exam.academic_year_label})`}
      actions={
        <Link
          to={`/analytics/exams/${exam.id}`}
          className={`${linkButton} bg-brand-600 text-white hover:bg-brand-700`}
        >
          Exam analytics
          <ArrowRight aria-hidden className="size-4" />
        </Link>
      }
    >
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile
          label="Students"
          value={data.student_count}
          hint={`${data.class_section_count} class sections`}
          icon={GraduationCap}
        />
        <StatTile
          label="Pass rate"
          value={fmtPct(summary.pass_percentage)}
          hint={`${summary.pass_count} of ${summary.student_count} passed every subject`}
          icon={Percent}
        />
        <StatTile
          label="Need support"
          value={data.at_risk_count}
          hint={`${data.at_risk_high_count} high priority`}
          icon={AlertTriangle}
        />
        <StatTile
          label="Mean score"
          value={fmtPct(summary.mean_percentage)}
          hint={`Median ${fmtPct(summary.median_percentage)}`}
          icon={TrendingUp}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <ChartCard title="Pass rate across exams" description="Pass % and mean score for recent exams with marks">
          {trend.length > 1 ? (
            <PercentLineChart
              data={trend}
              series={[
                { key: 'pass', name: 'Pass %' },
                { key: 'mean', name: 'Mean score %' },
              ]}
              ariaLabel="Line chart of pass percentage and mean score across exams"
            />
          ) : (
            <p className="py-10 text-center text-sm text-slate-500 dark:text-slate-400">
              The trend appears once a second exam has marks.
            </p>
          )}
        </ChartCard>
        <ChartCard title="Subject pass rate" description={exam.name}>
          <GroupedBarChart
            data={subjectBars}
            series={[{ key: 'pass', name: 'Pass %' }]}
            height="md"
            ariaLabel="Bar chart of pass percentage by subject"
          />
        </ChartCard>
      </div>

      <section className="mt-6" aria-labelledby="at-risk-heading">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 id="at-risk-heading" className="text-base font-semibold text-slate-900 dark:text-white">
            Students needing support
          </h2>
          {data.at_risk_count > data.at_risk_preview.length && (
            <Link
              to={`/analytics/exams/${exam.id}`}
              className="text-sm font-medium text-brand-700 hover:underline dark:text-brand-300"
            >
              View all {data.at_risk_count}
            </Link>
          )}
        </div>
        <AtRiskTable students={data.at_risk_preview} showDelta={data.previous_exam !== null} dense />
      </section>
    </PageWrapper>
  )
}
