import { AlertTriangle, CalendarDays, ChevronRight, LineChart } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Badge, EmptyState, GlassCard, PageSpinner, PageWrapper } from '@/components/ui'
import { useExamList } from '@/hooks/useAnalytics'
import { getErrorMessage } from '@/services/api'
import type { ExamListItem } from '@/types/analytics'

function groupByYear(items: readonly ExamListItem[]): [string, ExamListItem[]][] {
  const groups = new Map<string, ExamListItem[]>()
  for (const item of items) {
    const key = item.exam.academic_year_label
    groups.set(key, [...(groups.get(key) ?? []), item])
  }
  // Most recent year first; exams inside a year newest first.
  return [...groups.entries()].reverse().map(([year, exams]) => [year, [...exams].reverse()])
}

export default function AnalyticsPage() {
  const navigate = useNavigate()
  const { data, isLoading, error } = useExamList()
  const description = 'Pick an exam to see class, subject and student analytics.'

  if (isLoading) {
    return (
      <PageWrapper title="Analytics" description={description}>
        <PageSpinner label="Loading exams" />
      </PageWrapper>
    )
  }

  if (error || !data) {
    return (
      <PageWrapper title="Analytics" description={description}>
        <GlassCard hoverable={false}>
          <EmptyState icon={AlertTriangle} title="Could not load exams" description={getErrorMessage(error)} />
        </GlassCard>
      </PageWrapper>
    )
  }

  const withMarks = data.filter((e) => e.has_marks)
  const latest = withMarks.at(-1)

  return (
    <PageWrapper
      title="Analytics"
      description={description}
      actions={
        withMarks.length > 0 ? (
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <span>Exam</span>
            <select
              aria-label="Choose exam"
              defaultValue={latest ? String(latest.exam.id) : ''}
              onChange={(e) => navigate(`/analytics/exams/${e.target.value}`)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              {withMarks.map((item) => (
                <option key={item.exam.id} value={item.exam.id}>
                  {item.exam.name} ({item.exam.academic_year_label})
                </option>
              ))}
            </select>
          </label>
        ) : undefined
      }
    >
      {data.length === 0 ? (
        <GlassCard hoverable={false}>
          <EmptyState
            icon={LineChart}
            title="No exams yet"
            description="Create exams in Setup and import marks to unlock analytics."
          />
        </GlassCard>
      ) : (
        <div className="flex flex-col gap-6">
          {groupByYear(data).map(([year, exams]) => (
            <section key={year} aria-labelledby={`year-${year}`}>
              <h2 id={`year-${year}`} className="mb-3 text-sm font-semibold text-slate-500 dark:text-slate-400">
                Academic year {year}
              </h2>
              <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {exams.map((item) => (
                  <li key={item.exam.id}>
                    <button
                      type="button"
                      disabled={!item.has_marks}
                      onClick={() => navigate(`/analytics/exams/${item.exam.id}`)}
                      className="flex w-full cursor-pointer items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white/80 p-4 text-left transition-colors hover:border-brand-300 hover:bg-brand-50/60 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-800 dark:bg-slate-900/60 dark:hover:border-brand-700 dark:hover:bg-slate-800/60"
                    >
                      <div>
                        <p className="font-semibold text-slate-900 dark:text-white">{item.exam.name}</p>
                        <p className="mt-1 flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                          <CalendarDays aria-hidden className="size-3.5" />
                          {item.exam.held_on ?? `Exam #${item.exam.sequence}`}
                        </p>
                      </div>
                      {item.has_marks ? (
                        <ChevronRight aria-hidden className="size-5 text-brand-500" />
                      ) : (
                        <Badge tone="neutral">No marks yet</Badge>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </PageWrapper>
  )
}
