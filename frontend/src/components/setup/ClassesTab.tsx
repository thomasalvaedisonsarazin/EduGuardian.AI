import { Plus } from 'lucide-react'
import { useState } from 'react'
import { AnimatedInput, Badge, DataTable, EmptyState, GradientButton, type DataTableColumn } from '@/components/ui'
import { useAcademicYears, useClasses, useSetupMutation } from '@/hooks/useSetup'
import { setupService } from '@/services/setupService'
import type { AcademicYear, ID } from '@/types'
import type { ClassSectionInput, ClassSectionWithCount } from '@/types/setup'
import { classLabel, currentYearId, nameById } from './labels'
import { ErrorAlert, FormShell, Modal, RowActions, SelectField, Toolbar } from './shared'

export function ClassesTab() {
  const years = useAcademicYears()
  const [yearFilter, setYearFilter] = useState<string>('')
  const effectiveYear = yearFilter === '' ? currentYearId(years.data) : yearFilter === 'all' ? undefined : Number(yearFilter)
  const classes = useClasses(effectiveYear)
  const [editing, setEditing] = useState<{ cls: ClassSectionWithCount | null } | null>(null)
  const remove = useSetupMutation((id: number) => setupService.deleteClass(id))
  const yearName = nameById(years.data, (y) => y.label)

  const columns: DataTableColumn<ClassSectionWithCount>[] = [
    { id: 'class', header: 'Class', cell: (c) => <span className="font-medium">Class {classLabel(c)}</span> },
    { id: 'year', header: 'Academic year', cell: (c) => yearName(c.academic_year_id) },
    { id: 'students', header: 'Students', align: 'right', cell: (c) => <Badge tone="info">{c.student_count}</Badge> },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      cell: (c) => (
        <RowActions
          label={`class ${classLabel(c)}`}
          onEdit={() => setEditing({ cls: c })}
          onDelete={() => remove.mutateAsync(c.id)}
        />
      ),
    },
  ]

  return (
    <section aria-label="Classes">
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
        <GradientButton icon={Plus} onClick={() => setEditing({ cls: null })} disabled={!years.data?.length}>
          Add class
        </GradientButton>
      </Toolbar>
      <ErrorAlert error={classes.error} />
      <DataTable
        columns={columns}
        rows={classes.data ?? []}
        getRowId={(c) => c.id}
        loading={classes.isLoading || years.isLoading}
        caption="Classes"
        empty={
          <EmptyState
            title="No classes"
            description={years.data?.length ? 'Add a class section such as 10-A.' : 'Create an academic year first.'}
          />
        }
      />
      {editing && (
        <ClassForm
          cls={editing.cls}
          years={years.data ?? []}
          defaultYearId={effectiveYear ?? currentYearId(years.data)}
          onClose={() => setEditing(null)}
        />
      )}
    </section>
  )
}

interface ClassFormProps {
  cls: ClassSectionWithCount | null
  years: AcademicYear[]
  defaultYearId: ID | undefined
  onClose: () => void
}

function ClassForm({ cls, years, defaultYearId, onClose }: ClassFormProps) {
  const [yearId, setYearId] = useState(String(cls?.academic_year_id ?? defaultYearId ?? ''))
  const [grade, setGrade] = useState(cls ? String(cls.grade) : '')
  const [section, setSection] = useState(cls?.section ?? '')
  const [touched, setTouched] = useState(false)
  const save = useSetupMutation((input: ClassSectionInput) =>
    cls ? setupService.updateClass(cls.id, input) : setupService.createClass(input),
  )
  const gradeNum = Number(grade)
  const gradeError = !Number.isInteger(gradeNum) || gradeNum < 1 || gradeNum > 12 ? 'Grade must be 1–12' : undefined
  const sectionError = section.trim() ? undefined : 'Section is required'

  const submit = () => {
    setTouched(true)
    if (gradeError || sectionError || !yearId) return
    save.mutate(
      { academic_year_id: Number(yearId), grade: gradeNum, section: section.trim().toUpperCase() },
      { onSuccess: onClose },
    )
  }

  return (
    <Modal open title={cls ? `Edit class ${classLabel(cls)}` : 'Add class'} onClose={onClose}>
      <FormShell onSubmit={submit} onCancel={onClose} submitting={save.isPending} error={save.error}>
        <SelectField
          label="Academic year"
          value={yearId}
          onChange={setYearId}
          required
          placeholder="Select a year"
          options={years.map((y) => ({ value: String(y.id), label: y.label }))}
        />
        <div className="grid grid-cols-2 gap-3">
          <AnimatedInput
            label="Grade"
            type="number"
            min={1}
            max={12}
            value={grade}
            error={touched ? gradeError : undefined}
            onChange={(e) => setGrade(e.target.value)}
          />
          <AnimatedInput
            label="Section"
            placeholder="A"
            maxLength={10}
            value={section}
            error={touched ? sectionError : undefined}
            onChange={(e) => setSection(e.target.value)}
          />
        </div>
      </FormShell>
    </Modal>
  )
}
