import { ChevronLeft, ChevronRight, FileUp, Plus, Search } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import {
  AnimatedInput,
  Badge,
  DataTable,
  EmptyState,
  GlassCard,
  GradientButton,
  type DataTableColumn,
} from '@/components/ui'
import { useClasses, useImportStudents, useSetupMutation, useStudents } from '@/hooks/useSetup'
import { setupService } from '@/services/setupService'
import type { Student } from '@/types'
import type { ClassSectionWithCount, StudentImportResult, StudentInput } from '@/types/setup'
import { classLabel, nameById } from './labels'
import { ErrorAlert, FormShell, Modal, RowActions, SelectField, Toolbar } from './shared'

const STUDENTS_PAGE_SIZE = 25

export function StudentsTab() {
  const classes = useClasses()
  const [classFilter, setClassFilter] = useState('')
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [editing, setEditing] = useState<{ student: Student | null } | null>(null)
  const remove = useSetupMutation((id: number) => setupService.deleteStudent(id))

  useEffect(() => {
    const t = window.setTimeout(() => {
      setQ(search.trim())
      setPage(0)
    }, 300)
    return () => window.clearTimeout(t)
  }, [search])

  const students = useStudents({
    class_section_id: classFilter ? Number(classFilter) : undefined,
    q: q || undefined,
    limit: STUDENTS_PAGE_SIZE,
    offset: page * STUDENTS_PAGE_SIZE,
  })
  const total = students.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / STUDENTS_PAGE_SIZE))
  const className = nameById(classes.data, (c) => classLabel(c))

  const columns: DataTableColumn<Student>[] = [
    { id: 'pseudo', header: 'ID', cell: (s) => <Badge tone="brand">{s.pseudo_id}</Badge> },
    { id: 'adm', header: 'Admission no.', cell: (s) => <span className="font-mono text-xs">{s.admission_no}</span> },
    { id: 'name', header: 'Name', cell: (s) => <span className="font-medium">{s.full_name}</span> },
    { id: 'class', header: 'Class', cell: (s) => className(s.class_section_id) },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      cell: (s) => (
        <RowActions
          label={s.full_name}
          onEdit={() => setEditing({ student: s })}
          onDelete={() => remove.mutateAsync(s.id)}
        />
      ),
    },
  ]

  return (
    <section aria-label="Students" className="space-y-6">
      <ImportPanel />
      <div>
        <Toolbar>
          <div className="flex flex-wrap items-end gap-3">
            <SelectField
              label="Class"
              className="w-44"
              value={classFilter}
              onChange={(v) => {
                setClassFilter(v)
                setPage(0)
              }}
              placeholder="All classes"
              options={(classes.data ?? []).map((c) => ({ value: String(c.id), label: classLabel(c) }))}
            />
            <AnimatedInput
              label="Search"
              icon={Search}
              placeholder="Name, admission no. or ID"
              value={search}
              containerClassName="w-64"
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <GradientButton icon={Plus} onClick={() => setEditing({ student: null })} disabled={!classes.data?.length}>
            Add student
          </GradientButton>
        </Toolbar>
        <ErrorAlert error={students.error} />
        <DataTable
          columns={columns}
          rows={students.data?.items ?? []}
          getRowId={(s) => s.id}
          loading={students.isLoading}
          caption="Students"
          dense
          empty={<EmptyState title="No students found" description="Add students or import a CSV/Excel file." />}
        />
        <nav aria-label="Pagination" className="mt-3 flex items-center justify-between text-sm text-slate-600 dark:text-slate-300">
          <span>
            {total} student{total === 1 ? '' : 's'}
          </span>
          <div className="flex items-center gap-2">
            <GradientButton
              size="sm"
              variant="ghost"
              icon={ChevronLeft}
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              Prev
            </GradientButton>
            <span>
              Page {page + 1} of {pages}
            </span>
            <GradientButton
              size="sm"
              variant="ghost"
              iconRight={ChevronRight}
              disabled={page + 1 >= pages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </GradientButton>
          </div>
        </nav>
      </div>
      {editing && (
        <StudentForm student={editing.student} classes={classes.data ?? []} onClose={() => setEditing(null)} />
      )}
    </section>
  )
}

function ImportPanel() {
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const importer = useImportStudents()
  const [result, setResult] = useState<StudentImportResult | null>(null)

  const upload = () => {
    if (!file) return
    setResult(null)
    importer.mutate(file, {
      onSuccess: (data) => {
        setResult(data)
        setFile(null)
        if (inputRef.current) inputRef.current.value = ''
      },
    })
  }

  return (
    <GlassCard hoverable={false} padding="sm">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Bulk import students</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            CSV or Excel with columns <code>admission_no, full_name, grade, section</code>. Classes must exist in the
            current academic year; existing admission numbers are updated.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor={inputId} className="sr-only">
            Student file
          </label>
          <input
            id={inputId}
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="max-w-56 text-sm text-slate-600 file:mr-2 file:rounded-full file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-brand-700 dark:text-slate-300"
          />
          <GradientButton size="sm" icon={FileUp} onClick={upload} disabled={!file} loading={importer.isPending}>
            Import
          </GradientButton>
        </div>
      </div>
      <div className="mt-3 space-y-2">
        <ErrorAlert error={importer.error} />
        {result && (
          <div aria-live="polite" className="space-y-2 text-sm">
            <div className="flex flex-wrap gap-2">
              <Badge tone="success">{result.created} created</Badge>
              <Badge tone="info">{result.updated} updated</Badge>
              <Badge tone={result.errors.length ? 'danger' : 'neutral'}>{result.errors.length} errors</Badge>
            </div>
            {result.errors.length > 0 && (
              <ul className="max-h-40 list-inside list-disc overflow-y-auto text-xs text-rose-700 dark:text-rose-300">
                {result.errors.map((e) => (
                  <li key={`${e.row}-${e.message}`}>
                    Row {e.row}: {e.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </GlassCard>
  )
}

interface StudentFormProps {
  student: Student | null
  classes: ClassSectionWithCount[]
  onClose: () => void
}

function StudentForm({ student, classes, onClose }: StudentFormProps) {
  const [form, setForm] = useState({
    class_section_id: student ? String(student.class_section_id) : '',
    admission_no: student?.admission_no ?? '',
    full_name: student?.full_name ?? '',
  })
  const [touched, setTouched] = useState(false)
  const save = useSetupMutation((input: StudentInput) =>
    student ? setupService.updateStudent(student.id, input) : setupService.createStudent(input),
  )
  const valid = form.class_section_id !== '' && form.admission_no.trim() !== '' && form.full_name.trim() !== ''

  const submit = () => {
    setTouched(true)
    if (!valid) return
    save.mutate(
      {
        class_section_id: Number(form.class_section_id),
        admission_no: form.admission_no.trim(),
        full_name: form.full_name.trim(),
      },
      { onSuccess: onClose },
    )
  }

  return (
    <Modal open title={student ? `Edit ${student.pseudo_id}` : 'Add student'} onClose={onClose}>
      <FormShell onSubmit={submit} onCancel={onClose} submitting={save.isPending} error={save.error}>
        <SelectField
          label="Class"
          value={form.class_section_id}
          onChange={(v) => setForm({ ...form, class_section_id: v })}
          placeholder="Select a class"
          options={classes.map((c) => ({ value: String(c.id), label: classLabel(c) }))}
        />
        <AnimatedInput
          label="Admission number"
          value={form.admission_no}
          maxLength={50}
          error={touched && !form.admission_no.trim() ? 'Admission number is required' : undefined}
          onChange={(e) => setForm({ ...form, admission_no: e.target.value })}
        />
        <AnimatedInput
          label="Full name"
          value={form.full_name}
          maxLength={200}
          error={touched && !form.full_name.trim() ? 'Name is required' : undefined}
          onChange={(e) => setForm({ ...form, full_name: e.target.value })}
        />
        {touched && form.class_section_id === '' && <p className="text-sm text-rose-600">Select a class.</p>}
        {!student && (
          <p className="text-xs text-slate-500 dark:text-slate-400">A pseudonymous ID (S-xxxx) is assigned automatically.</p>
        )}
      </FormShell>
    </Modal>
  )
}
