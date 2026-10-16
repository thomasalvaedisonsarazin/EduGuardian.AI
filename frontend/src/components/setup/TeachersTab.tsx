import { Link2, Plus } from 'lucide-react'
import { useState } from 'react'
import { AnimatedInput, Badge, DataTable, EmptyState, GradientButton, type DataTableColumn } from '@/components/ui'
import {
  useClasses,
  useSetupMutation,
  useSubjects,
  useTeachers,
  useTeachingAssignments,
} from '@/hooks/useSetup'
import { setupService } from '@/services/setupService'
import type { Teacher, TeachingAssignment } from '@/types'
import type { TeacherInput, TeachingAssignmentInput } from '@/types/setup'
import { classLabel, nameById } from './labels'
import { CheckboxField, ErrorAlert, FormShell, Modal, RowActions, SelectField, Toolbar } from './shared'

export function TeachersTab() {
  const teachers = useTeachers()
  const assignments = useTeachingAssignments()
  const classes = useClasses()
  const subjects = useSubjects()
  const [editing, setEditing] = useState<{ teacher: Teacher | null } | null>(null)
  const [assigning, setAssigning] = useState(false)
  const removeTeacher = useSetupMutation((id: number) => setupService.deleteTeacher(id))
  const removeAssignment = useSetupMutation((id: number) => setupService.deleteTeachingAssignment(id))

  const teacherName = nameById(teachers.data, (t) => t.full_name)
  const className = nameById(classes.data, (c) => classLabel(c))
  const subjectName = nameById(subjects.data, (s) => s.name)

  const teacherColumns: DataTableColumn<Teacher>[] = [
    { id: 'name', header: 'Teacher', cell: (t) => <span className="font-medium">{t.full_name}</span> },
    {
      id: 'load',
      header: 'Assignments',
      cell: (t) => (assignments.data ?? []).filter((a) => a.teacher_id === t.id).length,
    },
    {
      id: 'login',
      header: 'Login',
      cell: (t) =>
        t.user_id ? (
          <Badge tone="success">
            <Link2 aria-hidden className="size-3" /> Linked
          </Badge>
        ) : (
          <Badge>Not linked</Badge>
        ),
    },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      cell: (t) => (
        <RowActions
          label={t.full_name}
          onEdit={() => setEditing({ teacher: t })}
          onDelete={() => removeTeacher.mutateAsync(t.id)}
        />
      ),
    },
  ]

  const assignmentColumns: DataTableColumn<TeachingAssignment>[] = [
    { id: 'teacher', header: 'Teacher', cell: (a) => teacherName(a.teacher_id) },
    { id: 'class', header: 'Class', cell: (a) => className(a.class_section_id) },
    { id: 'subject', header: 'Subject', cell: (a) => subjectName(a.subject_id) },
    {
      id: 'ct',
      header: 'Class teacher',
      cell: (a) => (a.is_class_teacher ? <Badge tone="accent">Class teacher</Badge> : null),
    },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      cell: (a) => (
        <RowActions
          label={`${subjectName(a.subject_id)} for ${className(a.class_section_id)}`}
          onDelete={() => removeAssignment.mutateAsync(a.id)}
        />
      ),
    },
  ]

  return (
    <section aria-label="Teachers" className="space-y-8">
      <div>
        <Toolbar>
          <p className="text-sm text-slate-500 dark:text-slate-400">Teachers and the classes/subjects they teach.</p>
          <GradientButton icon={Plus} onClick={() => setEditing({ teacher: null })}>
            Add teacher
          </GradientButton>
        </Toolbar>
        <ErrorAlert error={teachers.error} />
        <DataTable
          columns={teacherColumns}
          rows={teachers.data ?? []}
          getRowId={(t) => t.id}
          loading={teachers.isLoading}
          caption="Teachers"
          empty={<EmptyState title="No teachers yet" />}
        />
      </div>

      <div>
        <Toolbar>
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">Teaching assignments</h3>
          <GradientButton
            variant="secondary"
            icon={Plus}
            onClick={() => setAssigning(true)}
            disabled={!teachers.data?.length || !classes.data?.length || !subjects.data?.length}
          >
            Assign
          </GradientButton>
        </Toolbar>
        <DataTable
          columns={assignmentColumns}
          rows={assignments.data ?? []}
          getRowId={(a) => a.id}
          loading={assignments.isLoading}
          caption="Teaching assignments"
          dense
          empty={<EmptyState title="No assignments" description="Assign teachers to a class and subject." />}
        />
      </div>

      {editing && <TeacherForm teacher={editing.teacher} onClose={() => setEditing(null)} />}
      {assigning && <AssignmentForm onClose={() => setAssigning(false)} />}
    </section>
  )
}

function TeacherForm({ teacher, onClose }: { teacher: Teacher | null; onClose: () => void }) {
  const [fullName, setFullName] = useState(teacher?.full_name ?? '')
  const [touched, setTouched] = useState(false)
  const save = useSetupMutation((input: TeacherInput) =>
    teacher ? setupService.updateTeacher(teacher.id, input) : setupService.createTeacher(input),
  )
  const submit = () => {
    setTouched(true)
    if (!fullName.trim()) return
    save.mutate({ full_name: fullName.trim() }, { onSuccess: onClose })
  }
  return (
    <Modal open title={teacher ? 'Edit teacher' : 'Add teacher'} onClose={onClose}>
      <FormShell onSubmit={submit} onCancel={onClose} submitting={save.isPending} error={save.error}>
        <AnimatedInput
          label="Full name"
          value={fullName}
          maxLength={200}
          error={touched && !fullName.trim() ? 'Name is required' : undefined}
          onChange={(e) => setFullName(e.target.value)}
        />
      </FormShell>
    </Modal>
  )
}

function AssignmentForm({ onClose }: { onClose: () => void }) {
  const teachers = useTeachers()
  const classes = useClasses()
  const subjects = useSubjects()
  const [teacherId, setTeacherId] = useState('')
  const [classId, setClassId] = useState('')
  const [subjectId, setSubjectId] = useState('')
  const [isClassTeacher, setIsClassTeacher] = useState(false)
  const [touched, setTouched] = useState(false)
  const save = useSetupMutation((input: TeachingAssignmentInput) => setupService.createTeachingAssignment(input))
  const valid = teacherId !== '' && classId !== '' && subjectId !== ''

  const submit = () => {
    setTouched(true)
    if (!valid) return
    save.mutate(
      {
        teacher_id: Number(teacherId),
        class_section_id: Number(classId),
        subject_id: Number(subjectId),
        is_class_teacher: isClassTeacher,
      },
      { onSuccess: onClose },
    )
  }

  return (
    <Modal open title="Assign teacher" onClose={onClose}>
      <FormShell onSubmit={submit} onCancel={onClose} submitting={save.isPending} error={save.error} submitLabel="Assign">
        <SelectField
          label="Teacher"
          value={teacherId}
          onChange={setTeacherId}
          placeholder="Select a teacher"
          options={(teachers.data ?? []).map((t) => ({ value: String(t.id), label: t.full_name }))}
        />
        <SelectField
          label="Class"
          value={classId}
          onChange={setClassId}
          placeholder="Select a class"
          options={(classes.data ?? []).map((c) => ({ value: String(c.id), label: classLabel(c) }))}
        />
        <SelectField
          label="Subject"
          value={subjectId}
          onChange={setSubjectId}
          placeholder="Select a subject"
          options={(subjects.data ?? []).map((s) => ({ value: String(s.id), label: s.name }))}
        />
        <CheckboxField label="Class teacher for this section" checked={isClassTeacher} onChange={setIsClassTeacher} />
        {touched && !valid && <p className="text-sm text-rose-600">Teacher, class and subject are required.</p>}
      </FormShell>
    </Modal>
  )
}
