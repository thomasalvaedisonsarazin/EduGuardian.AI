import { ListChecks, Plus } from 'lucide-react'
import { useState } from 'react'
import { AnimatedInput, Badge, DataTable, EmptyState, GradientButton, Spinner, type DataTableColumn } from '@/components/ui'
import { useAcademicYears, useExams, useSetupMutation } from '@/hooks/useSetup'
import { setupService } from '@/services/setupService'
import type { AcademicYear, Exam, ID } from '@/types'
import type { ExamInput } from '@/types/setup'
import { ExamSubjectsEditor } from './ExamSubjectsEditor'
import { currentYearId, nameById } from './labels'
import { ErrorAlert, FormShell, Modal, RowActions, SelectField, Toolbar } from './shared'

export function ExamsTab() {
  const years = useAcademicYears()
  const [yearFilter, setYearFilter] = useState('')
  const effectiveYear = yearFilter === '' ? currentYearId(years.data) : yearFilter === 'all' ? undefined : Number(yearFilter)
  const exams = useExams(effectiveYear)
  const [editing, setEditing] = useState<{ exam: Exam | null } | null>(null)
  const [configuring, setConfiguring] = useState<Exam | null>(null)
  const remove = useSetupMutation((id: number) => setupService.deleteExam(id))
  const yearName = nameById(years.data, (y) => y.label)

  const columns: DataTableColumn<Exam>[] = [
    { id: 'seq', header: '#', cell: (e) => <Badge tone="neutral">{e.sequence}</Badge> },
    { id: 'name', header: 'Exam', cell: (e) => <span className="font-medium">{e.name}</span> },
    { id: 'year', header: 'Academic year', cell: (e) => yearName(e.academic_year_id) },
    { id: 'held', header: 'Held on', cell: (e) => e.held_on ?? '—' },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      cell: (e) => (
        <RowActions
          label={e.name}
          onEdit={() => setEditing({ exam: e })}
          onDelete={() => remove.mutateAsync(e.id)}
          extra={
            <GradientButton size="sm" variant="secondary" icon={ListChecks} onClick={() => setConfiguring(e)}>
              Subjects
            </GradientButton>
          }
        />
      ),
    },
  ]

  return (
    <section aria-label="Exams">
      <Toolbar>
        <SelectField
          label="Academic year"
          className="w-56"
          value={yearFilter === '' && effectiveYear !== undefined ? String(effectiveYear) : yearFilter}
          onChange={setYearFilter}
          options={[
            { value: 'all', label: 'All years' },
            ...(years.data ?? []).map((y) => ({ value: String(y.id), label: y.label + (y.is_current ? ' (current)' : '') })),
          ]}
        />
        <GradientButton icon={Plus} onClick={() => setEditing({ exam: null })} disabled={!years.data?.length}>
          Add exam
        </GradientButton>
      </Toolbar>
      <ErrorAlert error={exams.error} />
      {years.isLoading ? (
        <Spinner showLabel />
      ) : (
        <DataTable
          columns={columns}
          rows={exams.data ?? []}
          getRowId={(e) => e.id}
          loading={exams.isLoading}
          caption="Exams"
          empty={<EmptyState title="No exams" description="Add an exam, then configure its subjects and max marks." />}
        />
      )}
      {editing && (
        <ExamForm
          exam={editing.exam}
          years={years.data ?? []}
          defaultYearId={effectiveYear ?? currentYearId(years.data)}
          nextSequence={(exams.data?.reduce((m, e) => Math.max(m, e.sequence), 0) ?? 0) + 1}
          onClose={() => setEditing(null)}
        />
      )}
      {configuring && (
        <Modal open wide title={`Subjects — ${configuring.name}`} onClose={() => setConfiguring(null)}>
          <ExamSubjectsEditor examId={configuring.id} onDone={() => setConfiguring(null)} />
        </Modal>
      )}
    </section>
  )
}

interface ExamFormProps {
  exam: Exam | null
  years: AcademicYear[]
  defaultYearId: ID | undefined
  nextSequence: number
  onClose: () => void
}

function ExamForm({ exam, years, defaultYearId, nextSequence, onClose }: ExamFormProps) {
  const [yearId, setYearId] = useState(String(exam?.academic_year_id ?? defaultYearId ?? ''))
  const [name, setName] = useState(exam?.name ?? '')
  const [sequence, setSequence] = useState(String(exam?.sequence ?? nextSequence))
  const [heldOn, setHeldOn] = useState(exam?.held_on ?? '')
  const [touched, setTouched] = useState(false)
  const save = useSetupMutation((input: ExamInput) =>
    exam ? setupService.updateExam(exam.id, input) : setupService.createExam(input),
  )
  const seqNum = Number(sequence)
  const seqError = Number.isInteger(seqNum) && seqNum >= 1 ? undefined : 'Sequence must be a positive whole number'

  const submit = () => {
    setTouched(true)
    if (!name.trim() || seqError || !yearId) return
    save.mutate(
      { academic_year_id: Number(yearId), name: name.trim(), sequence: seqNum, held_on: heldOn || null },
      { onSuccess: onClose },
    )
  }

  return (
    <Modal open title={exam ? 'Edit exam' : 'Add exam'} onClose={onClose}>
      <FormShell onSubmit={submit} onCancel={onClose} submitting={save.isPending} error={save.error}>
        <SelectField
          label="Academic year"
          value={yearId}
          onChange={setYearId}
          placeholder="Select a year"
          options={years.map((y) => ({ value: String(y.id), label: y.label }))}
        />
        <AnimatedInput
          label="Name"
          placeholder="Unit Test 1"
          value={name}
          maxLength={100}
          error={touched && !name.trim() ? 'Name is required' : undefined}
          onChange={(e) => setName(e.target.value)}
        />
        <div className="grid grid-cols-2 gap-3">
          <AnimatedInput
            label="Sequence"
            type="number"
            min={1}
            value={sequence}
            hint="Order of exams within the year"
            error={touched ? seqError : undefined}
            onChange={(e) => setSequence(e.target.value)}
          />
          <AnimatedInput label="Held on" type="date" value={heldOn} onChange={(e) => setHeldOn(e.target.value)} />
        </div>
      </FormShell>
    </Modal>
  )
}
