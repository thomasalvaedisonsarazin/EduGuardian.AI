import { AlertTriangle, CheckCircle2, FileBarChart } from 'lucide-react'
import { useState } from 'react'
import { GenerateReportForm, ReportList } from '@/components/reports'
import { EmptyState, GlassCard, PageSpinner, PageWrapper } from '@/components/ui'
import { useAuth } from '@/hooks/useAuth'
import {
  useDeleteReport,
  useDownloadReport,
  useGenerateReport,
  useReportClasses,
  useReportExams,
  useReportList,
  useReportTeachers,
} from '@/hooks/useReports'
import { getErrorMessage } from '@/services/api'
import { REPORT_KIND_LABELS, type ReportCreateInput, type ReportItem } from '@/types/reports'

interface Notice {
  tone: 'success' | 'error'
  text: string
}

export default function ReportsPage() {
  const { role } = useAuth()
  const exams = useReportExams()
  const classes = useReportClasses()
  const teachers = useReportTeachers()
  const reports = useReportList()
  const generate = useGenerateReport()
  const remove = useDeleteReport()
  const download = useDownloadReport()
  const [notice, setNotice] = useState<Notice | null>(null)

  const description = 'Principal-ready PDF and Excel reports, computed deterministically from your marks.'

  const handleGenerate = (input: ReportCreateInput) => {
    setNotice(null)
    generate.mutate(input, {
      onSuccess: (report) =>
        setNotice({
          tone: 'success',
          text: `${REPORT_KIND_LABELS[report.kind]} report for ${report.exam_name ?? 'the exam'} is ready.`,
        }),
      onError: (err) => setNotice({ tone: 'error', text: getErrorMessage(err) }),
    })
  }

  const handleDownload = (report: ReportItem) => {
    download.mutate(report, { onError: (err) => setNotice({ tone: 'error', text: getErrorMessage(err) }) })
  }

  const handleDelete = (report: ReportItem) => {
    if (!window.confirm(`Delete ${REPORT_KIND_LABELS[report.kind]} report #${report.id}? This cannot be undone.`)) return
    remove.mutate(report.id, {
      onSuccess: () => setNotice({ tone: 'success', text: `Report #${report.id} deleted.` }),
      onError: (err) => setNotice({ tone: 'error', text: getErrorMessage(err) }),
    })
  }

  const lookupsLoading = exams.isLoading || classes.isLoading || teachers.isLoading

  return (
    <PageWrapper title="Reports" description={description}>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
        <GlassCard hoverable={false} className="h-fit">
          <h2 className="mb-4 flex items-center gap-2 text-base font-semibold text-slate-900 dark:text-white">
            <FileBarChart aria-hidden className="size-5 text-brand-600" />
            Generate report
          </h2>
          {lookupsLoading ? (
            <PageSpinner label="Loading exams" />
          ) : exams.error ? (
            <EmptyState icon={AlertTriangle} title="Could not load exams" description={getErrorMessage(exams.error)} />
          ) : (exams.data ?? []).length === 0 ? (
            <EmptyState title="No exams yet" description="Create an exam in Setup and import marks first." />
          ) : (
            <GenerateReportForm
              exams={exams.data ?? []}
              classes={classes.data ?? []}
              teachers={teachers.data ?? []}
              userRole={role}
              submitting={generate.isPending}
              onSubmit={handleGenerate}
            />
          )}
          {notice && (
            <p
              role={notice.tone === 'error' ? 'alert' : 'status'}
              className={
                notice.tone === 'error'
                  ? 'mt-4 flex items-start gap-2 rounded-xl bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-900/30 dark:text-rose-300'
                  : 'mt-4 flex items-start gap-2 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
              }
            >
              {notice.tone === 'error' ? (
                <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
              ) : (
                <CheckCircle2 aria-hidden className="mt-0.5 size-4 shrink-0" />
              )}
              {notice.text}
            </p>
          )}
        </GlassCard>

        <section aria-labelledby="reports-list-title" className="min-w-0">
          <h2 id="reports-list-title" className="mb-3 text-base font-semibold text-slate-900 dark:text-white">
            Generated reports
          </h2>
          {reports.error ? (
            <GlassCard hoverable={false}>
              <EmptyState icon={AlertTriangle} title="Could not load reports" description={getErrorMessage(reports.error)} />
            </GlassCard>
          ) : (
            <ReportList
              reports={reports.data ?? []}
              loading={reports.isLoading}
              canDelete={role === 'school_admin'}
              downloadingId={download.isPending ? (download.variables?.id ?? null) : null}
              deletingId={remove.isPending ? (remove.variables ?? null) : null}
              onDownload={handleDownload}
              onDelete={handleDelete}
            />
          )}
        </section>
      </div>
    </PageWrapper>
  )
}
