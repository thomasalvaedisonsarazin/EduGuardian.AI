import { Plus } from 'lucide-react'
import { useState } from 'react'
import { AnimatedInput, Badge, DataTable, EmptyState, GradientButton, type DataTableColumn } from '@/components/ui'
import { useSetupMutation, useSubjects } from '@/hooks/useSetup'
import { setupService } from '@/services/setupService'
import type { Subject } from '@/types'
import type { SubjectInput } from '@/types/setup'
import { ErrorAlert, FormShell, Modal, RowActions, Toolbar } from './shared'

export function SubjectsTab() {
  const subjects = useSubjects()
  const [editing, setEditing] = useState<{ subject: Subject | null } | null>(null)
  const remove = useSetupMutation((id: number) => setupService.deleteSubject(id))

  const columns: DataTableColumn<Subject>[] = [
    { id: 'name', header: 'Subject', cell: (s) => <span className="font-medium">{s.name}</span> },
    { id: 'code', header: 'Code', cell: (s) => <Badge tone="brand">{s.code}</Badge> },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      cell: (s) => (
        <RowActions
          label={s.name}
          onEdit={() => setEditing({ subject: s })}
          onDelete={() => remove.mutateAsync(s.id)}
        />
      ),
    },
  ]

  return (
    <section aria-label="Subjects">
      <Toolbar>
        <p className="text-sm text-slate-500 dark:text-slate-400">Subject codes must be unique within the school.</p>
        <GradientButton icon={Plus} onClick={() => setEditing({ subject: null })}>
          Add subject
        </GradientButton>
      </Toolbar>
      <ErrorAlert error={subjects.error} />
      <DataTable
        columns={columns}
        rows={subjects.data ?? []}
        getRowId={(s) => s.id}
        loading={subjects.isLoading}
        caption="Subjects"
        empty={<EmptyState title="No subjects yet" />}
      />
      {editing && <SubjectForm subject={editing.subject} onClose={() => setEditing(null)} />}
    </section>
  )
}

function SubjectForm({ subject, onClose }: { subject: Subject | null; onClose: () => void }) {
  const [form, setForm] = useState<SubjectInput>({ name: subject?.name ?? '', code: subject?.code ?? '' })
  const [touched, setTouched] = useState(false)
  const save = useSetupMutation((input: SubjectInput) =>
    subject ? setupService.updateSubject(subject.id, input) : setupService.createSubject(input),
  )
  const valid = form.name.trim() !== '' && form.code.trim() !== ''

  const submit = () => {
    setTouched(true)
    if (!valid) return
    save.mutate({ name: form.name.trim(), code: form.code.trim().toUpperCase() }, { onSuccess: onClose })
  }

  return (
    <Modal open title={subject ? 'Edit subject' : 'Add subject'} onClose={onClose}>
      <FormShell onSubmit={submit} onCancel={onClose} submitting={save.isPending} error={save.error}>
        <AnimatedInput
          label="Name"
          placeholder="Mathematics"
          value={form.name}
          maxLength={100}
          error={touched && !form.name.trim() ? 'Name is required' : undefined}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <AnimatedInput
          label="Code"
          placeholder="MATH"
          value={form.code}
          maxLength={20}
          error={touched && !form.code.trim() ? 'Code is required' : undefined}
          onChange={(e) => setForm({ ...form, code: e.target.value })}
        />
      </FormShell>
    </Modal>
  )
}
