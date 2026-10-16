import { Badge, DataTable, EmptyState, type DataTableColumn } from '@/components/ui'
import { useImportList } from '@/hooks/useImports'
import { getErrorMessage } from '@/services/api'
import type { ImportBatchListItem } from '@/types/imports'
import { formatDateTime, STATUS_TONE } from './labels'

const columns: DataTableColumn<ImportBatchListItem>[] = [
  { id: 'file', header: 'File', cell: (b) => <span className="font-medium">{b.filename}</span> },
  { id: 'exam', header: 'Exam', cell: (b) => b.exam_name ?? `#${b.exam_id}` },
  { id: 'status', header: 'Status', cell: (b) => <Badge tone={STATUS_TONE[b.status]}>{b.status}</Badge> },
  { id: 'rows', header: 'Rows', cell: (b) => b.row_count, align: 'right' },
  {
    id: 'issues',
    header: 'Issues',
    cell: (b) => (
      <span className="inline-flex gap-1">
        <Badge tone={b.summary.errors > 0 ? 'danger' : 'neutral'}>{b.summary.errors} err</Badge>
        <Badge tone={b.summary.warnings > 0 ? 'warning' : 'neutral'}>{b.summary.warnings} warn</Badge>
      </span>
    ),
  },
  { id: 'when', header: 'Uploaded', cell: (b) => formatDateTime(b.created_at) },
]

/** Recent import batches for the active school; clicking a row reopens it in the wizard. */
export function RecentImports({ onOpen }: { onOpen: (batch: ImportBatchListItem) => void }) {
  const { data, isLoading, error } = useImportList()
  if (error) return <p className="text-sm text-rose-600 dark:text-rose-400">{getErrorMessage(error)}</p>
  return (
    <DataTable
      dense
      caption="Recent imports"
      columns={columns}
      rows={(data ?? []).slice(0, 10)}
      loading={isLoading}
      getRowId={(b) => b.id}
      onRowClick={onOpen}
      empty={<EmptyState title="No imports yet" description="Uploaded marks files will appear here." />}
    />
  )
}
