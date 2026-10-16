import { ArrowLeft, ArrowRight, BarChart3, CheckCircle2, Download, Upload, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  FileDropzone,
  IssueSummary,
  IssueTable,
  MappingEditor,
  PreviewTable,
  RecentImports,
  STATUS_TONE,
  WizardSteps,
  type WizardStep,
} from '@/components/imports'
import { selectClass } from '@/components/imports/styles'
import { Badge, EmptyState, GlassCard, GradientButton, PageWrapper, Spinner } from '@/components/ui'
import {
  useCommitImport,
  useImportBatch,
  useImportExams,
  useRejectImport,
  useUpdateMapping,
  useUploadImport,
} from '@/hooks/useImports'
import { getErrorMessage } from '@/services/api'
import { importService } from '@/services/importService'
import type { ID } from '@/types'
import type { CommitResult, ImportBatchDetail, ImportBatchListItem } from '@/types/imports'

function ErrorText({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <p role="alert" className="text-sm text-rose-600 dark:text-rose-400">
      {getErrorMessage(error)}
    </p>
  )
}

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{title}</h2>
      {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}
    </div>
  )
}

// --- step 1 --------------------------------------------------------------------------------
function UploadStep({ onUploaded }: { onUploaded: (batch: ImportBatchDetail) => void }) {
  const exams = useImportExams()
  const upload = useUploadImport()
  const [examId, setExamId] = useState<ID | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [templateError, setTemplateError] = useState<unknown>(null)
  const [downloading, setDownloading] = useState(false)

  const downloadTemplate = async () => {
    if (examId === null) return
    setDownloading(true)
    setTemplateError(null)
    try {
      await importService.downloadTemplate(examId)
    } catch (err) {
      setTemplateError(err)
    } finally {
      setDownloading(false)
    }
  }

  const sortedExams = [...(exams.data ?? [])].sort((a, b) => a.sequence - b.sequence || a.name.localeCompare(b.name))

  return (
    <GlassCard hoverable={false}>
      <SectionTitle title="1. Choose an exam and upload marks" subtitle="CSV or Excel with an admission-number column and one column per subject." />
      <div className="space-y-5">
        {exams.isLoading ? (
          <Spinner showLabel label="Loading exams" />
        ) : exams.error ? (
          <div className="rounded-xl bg-rose-50 p-4 text-sm text-rose-700 dark:bg-rose-900/30 dark:text-rose-300">
            Could not load exams: {getErrorMessage(exams.error)}. Create exams under{' '}
            <Link to="/setup" className="font-semibold underline">
              Academic setup
            </Link>{' '}
            first.
          </div>
        ) : sortedExams.length === 0 ? (
          <EmptyState
            title="No exams yet"
            description={
              <>
                Create an exam with subject max/pass marks in <Link to="/setup" className="underline">Academic setup</Link>.
              </>
            }
          />
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-200">
              Exam
              <select
                className={`${selectClass} h-11 min-w-64`}
                value={examId ?? ''}
                onChange={(e) => setExamId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Select an exam…</option>
                {sortedExams.map((exam) => (
                  <option key={exam.id} value={exam.id}>
                    {exam.name}
                    {exam.held_on ? ` (${exam.held_on})` : ''}
                  </option>
                ))}
              </select>
            </label>
            <GradientButton
              variant="secondary"
              icon={Download}
              disabled={examId === null}
              loading={downloading}
              onClick={() => void downloadTemplate()}
            >
              Download template
            </GradientButton>
          </div>
        )}
        <ErrorText error={templateError} />
        <FileDropzone file={file} onFile={setFile} disabled={upload.isPending} />
        <ErrorText error={upload.error} />
        <GradientButton
          icon={Upload}
          disabled={examId === null || file === null}
          loading={upload.isPending}
          onClick={() => {
            if (examId !== null && file) upload.mutate({ examId, file }, { onSuccess: onUploaded })
          }}
        >
          Upload &amp; validate
        </GradientButton>
      </div>
    </GlassCard>
  )
}

// --- step 2 --------------------------------------------------------------------------------
function MappingStep({ batch, onDone }: { batch: ImportBatchDetail; onDone: () => void }) {
  const update = useUpdateMapping(batch.id)
  const editable = batch.status === 'validated' || batch.status === 'uploaded'
  return (
    <GlassCard hoverable={false}>
      <SectionTitle
        title="2. Check the column mapping"
        subtitle="We matched columns to subjects automatically. Fix anything that looks wrong."
      />
      {editable ? (
        <MappingEditor
          key={`${batch.id}-${JSON.stringify(batch.column_map)}`}
          headers={batch.headers}
          initial={batch.column_map}
          subjects={batch.exam_subjects}
          saving={update.isPending}
          onSubmit={(mapping) => update.mutate(mapping, { onSuccess: onDone })}
        />
      ) : (
        <p className="text-sm text-slate-500">This import is {batch.status}; the mapping can no longer change.</p>
      )}
      <div className="mt-3">
        <ErrorText error={update.error} />
      </div>
      <div className="mt-6 flex justify-end">
        <GradientButton variant="ghost" iconRight={ArrowRight} onClick={onDone}>
          Mapping looks right
        </GradientButton>
      </div>
    </GlassCard>
  )
}

// --- step 3 --------------------------------------------------------------------------------
function ReviewStep({
  batch,
  onBack,
  onNext,
  onRejected,
}: {
  batch: ImportBatchDetail
  onBack: () => void
  onNext: () => void
  onRejected: () => void
}) {
  const reject = useRejectImport(batch.id)
  return (
    <div className="space-y-6">
      <GlassCard hoverable={false}>
        <SectionTitle title="3. Review validation results" subtitle={`${batch.filename} · ${batch.exam_name ?? ''}`} />
        <IssueSummary summary={batch.summary} rowCount={batch.row_count} text={batch.summary_text} />
        {!batch.can_commit && batch.status === 'validated' && (
          <p className="mt-3 text-sm text-rose-600 dark:text-rose-400">
            Fix the errors in your file (or the mapping) and upload again before committing.
          </p>
        )}
      </GlassCard>
      <GlassCard hoverable={false}>
        <SectionTitle title="Issues" />
        <IssueTable issues={batch.issues} />
      </GlassCard>
      <GlassCard hoverable={false}>
        <SectionTitle title="Preview" subtitle="Cells with errors are red; warnings are amber." />
        <PreviewTable batch={batch} />
      </GlassCard>
      <ErrorText error={reject.error} />
      <div className="flex flex-wrap justify-between gap-2">
        <GradientButton variant="ghost" icon={ArrowLeft} onClick={onBack}>
          Back to mapping
        </GradientButton>
        <div className="flex gap-2">
          {batch.status === 'validated' && (
            <GradientButton
              variant="danger"
              icon={XCircle}
              loading={reject.isPending}
              onClick={() => reject.mutate(undefined, { onSuccess: onRejected })}
            >
              Discard import
            </GradientButton>
          )}
          <GradientButton iconRight={ArrowRight} disabled={!batch.can_commit} onClick={onNext}>
            Continue to commit
          </GradientButton>
        </div>
      </div>
    </div>
  )
}

// --- step 4 --------------------------------------------------------------------------------
function CommitStep({ batch, onBack, onRestart }: { batch: ImportBatchDetail; onBack: () => void; onRestart: () => void }) {
  const commit = useCommitImport(batch.id)
  const navigate = useNavigate()
  const [result, setResult] = useState<CommitResult | null>(null)
  const committed = result !== null || batch.status === 'committed'

  return (
    <GlassCard hoverable={false}>
      <SectionTitle title="4. Confirm & commit" />
      {committed ? (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300">
            <CheckCircle2 aria-hidden className="size-6" />
            <span className="font-semibold">Marks committed for {batch.exam_name ?? 'the exam'}.</span>
          </div>
          {result && (
            <div className="flex flex-wrap gap-2" aria-label="Commit result">
              <Badge tone="success">{result.inserted} inserted</Badge>
              <Badge tone="info">{result.updated} updated</Badge>
              <Badge tone="warning">{result.absent} absent</Badge>
              <Badge tone="neutral">{result.skipped} blank skipped</Badge>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <GradientButton icon={BarChart3} onClick={() => void navigate(`/analytics/exams/${batch.exam_id}`)}>
              View exam analytics
            </GradientButton>
            <GradientButton variant="secondary" onClick={() => void navigate('/analytics')}>
              All analytics
            </GradientButton>
            <GradientButton variant="ghost" icon={Upload} onClick={onRestart}>
              Import another file
            </GradientButton>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            {batch.row_count} rows from <span className="font-medium">{batch.filename}</span> will be saved to{' '}
            <span className="font-medium">{batch.exam_name}</span>. Existing marks for the same student and subject are
            updated; blank cells are skipped.
          </p>
          <IssueSummary summary={batch.summary} rowCount={batch.row_count} />
          <ErrorText error={commit.error} />
          <div className="flex flex-wrap justify-between gap-2">
            <GradientButton variant="ghost" icon={ArrowLeft} onClick={onBack}>
              Back
            </GradientButton>
            <GradientButton
              icon={CheckCircle2}
              disabled={!batch.can_commit}
              loading={commit.isPending}
              onClick={() => commit.mutate(undefined, { onSuccess: setResult })}
            >
              Commit marks
            </GradientButton>
          </div>
        </div>
      )}
    </GlassCard>
  )
}

// --- page ----------------------------------------------------------------------------------
export default function ImportMarksPage() {
  const [step, setStep] = useState<WizardStep>(1)
  const [batchId, setBatchId] = useState<ID | null>(null)
  const batchQuery = useImportBatch(batchId)
  const batch = batchQuery.data ?? null

  const maxReachable: WizardStep = batch ? (batch.can_commit || batch.status === 'committed' ? 4 : 3) : 1

  const open = (b: ImportBatchListItem | ImportBatchDetail) => {
    setBatchId(b.id)
    setStep(b.status === 'committed' ? 4 : 3)
  }
  const restart = () => {
    setBatchId(null)
    setStep(1)
  }

  return (
    <PageWrapper
      title="Import Marks"
      description="Upload a marks sheet, let the Data Quality Agent check it, then commit."
      actions={batch && <Badge tone={STATUS_TONE[batch.status]}>{batch.status}</Badge>}
    >
      <div className="space-y-6">
        <WizardSteps current={step} maxReachable={maxReachable} onSelect={setStep} />

        {step === 1 && (
          <UploadStep
            onUploaded={(b) => {
              setBatchId(b.id)
              setStep(2)
            }}
          />
        )}
        {step > 1 && batchQuery.isLoading && <Spinner showLabel label="Loading import" />}
        {step > 1 && batchQuery.error && <ErrorText error={batchQuery.error} />}
        {step === 2 && batch && <MappingStep batch={batch} onDone={() => setStep(3)} />}
        {step === 3 && batch && (
          <ReviewStep batch={batch} onBack={() => setStep(2)} onNext={() => setStep(4)} onRejected={restart} />
        )}
        {step === 4 && batch && <CommitStep batch={batch} onBack={() => setStep(3)} onRestart={restart} />}

        <GlassCard hoverable={false}>
          <SectionTitle title="Recent imports" subtitle="Click an import to review it again." />
          <RecentImports onOpen={open} />
        </GlassCard>
      </div>
    </PageWrapper>
  )
}
