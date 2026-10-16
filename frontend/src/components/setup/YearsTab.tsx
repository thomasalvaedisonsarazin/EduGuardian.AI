import { Plus } from 'lucide-react'
import { useState } from 'react'
import { AnimatedInput, Badge, DataTable, EmptyState, GradientButton, type DataTableColumn } from '@/components/ui'
import { useAcademicYears, useSetupMutation } from '@/hooks/useSetup'
import { setupService } from '@/services/setupService'
import type { AcademicYear } from '@/types'
import type { AcademicYearInput } from '@/types/setup'
import { CheckboxField, ErrorAlert, FormShell, Modal, RowActions, Toolbar } from './shared'

interface Editing {
  year: AcademicYear | null
}

export function YearsTab() {
  const years = useAcademicYears()
  const [editing, setEditing] = useState<Editing | null>(null)
  const remove = useSetupMutation((id: number) => setupService.deleteAcademicYear(id))

  const columns: DataTableColumn<AcademicYear>[] = [
    { id: 'label', header: 'Academic year', cell: (y) => <span className="font-medium">{y.label}</span> },
    {
      id: 'current',
      header: 'Status',
      cell: (y) => (y.is_current ? <Badge tone="success" dot>Current</Badge> : <Badge>Past / upcoming</Badge>),
    },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      cell: (y) => (
        <RowActions label={y.label} onEdit={() => setEditing({ year: y })} onDelete={() => remove.mutateAsync(y.id)} />
      ),
    },
  ]

  return (
    <section aria-label="Academic years">
      <Toolbar>
        <p className="text-sm text-slate-500 dark:text-slate-400">Only one academic year can be current.</p>
        <GradientButton icon={Plus} onClick={() => setEditing({ year: null })}>
          Add year
        </GradientButton>
      </Toolbar>
      <ErrorAlert error={years.error} />
      <DataTable
        columns={columns}
        rows={years.data ?? []}
        getRowId={(y) => y.id}
        loading={years.isLoading}
        caption="Academic years"
        empty={<EmptyState title="No academic years" description="Add your first academic year, e.g. 2026-27." />}
      />
      {editing && <YearForm year={editing.year} onClose={() => setEditing(null)} />}
    </section>
  )
}

function YearForm({ year, onClose }: { year: AcademicYear | null; onClose: () => void }) {
  const [form, setForm] = useState<AcademicYearInput>({
    label: year?.label ?? '',
    is_current: year?.is_current ?? false,
  })
  const [touched, setTouched] = useState(false)
  const save = useSetupMutation((input: AcademicYearInput) =>
    year ? setupService.updateAcademicYear(year.id, input) : setupService.createAcademicYear(input),
  )
  const labelError = touched && !form.label.trim() ? 'Label is required' : undefined

  const submit = () => {
    setTouched(true)
    if (!form.label.trim()) return
    save.mutate({ ...form, label: form.label.trim() }, { onSuccess: onClose })
  }

  return (
    <Modal open title={year ? 'Edit academic year' : 'Add academic year'} onClose={onClose}>
      <FormShell onSubmit={submit} onCancel={onClose} submitting={save.isPending} error={save.error}>
        <AnimatedInput
          label="Label"
          placeholder="2026-27"
          value={form.label}
          maxLength={20}
          error={labelError}
          onChange={(e) => setForm({ ...form, label: e.target.value })}
        />
        <CheckboxField
          label="Current academic year"
          checked={form.is_current}
          onChange={(is_current) => setForm({ ...form, is_current })}
        />
      </FormShell>
    </Modal>
  )
}
