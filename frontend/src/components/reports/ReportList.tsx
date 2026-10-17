import { Bot, Download, FileSpreadsheet, FileText, Trash2 } from 'lucide-react'
import { Badge, DataTable, EmptyState, GradientButton, type BadgeTone, type DataTableColumn } from '@/components/ui'
import type { ID } from '@/types'
import { REPORT_KIND_LABELS, type ReportItem, type ReportKind } from '@/types/reports'
import { formatCreatedAt, formatSize } from './format'

export interface ReportListProps {
  reports: readonly ReportItem[]
  loading?: boolean
  canDelete: boolean
  downloadingId?: ID | null
  deletingId?: ID | null
  onDownload: (report: ReportItem) => void
  onDelete: (report: ReportItem) => void
}

const KIND_TONES: Record<ReportKind, BadgeTone> = {
  principal: 'brand',
  class_teacher: 'info',
  subject_teacher: 'accent',
}

export function ReportList({
  reports,
  loading = false,
  canDelete,
  downloadingId = null,
  deletingId = null,
  onDownload,
  onDelete,
}: ReportListProps) {
  const columns: DataTableColumn<ReportItem>[] = [
    {
      id: 'kind',
      header: 'Report',
      cell: (r) => (
        <div className="flex flex-col items-start gap-1">
          <Badge tone={KIND_TONES[r.kind]}>{REPORT_KIND_LABELS[r.kind]}</Badge>
          {r.run_id !== null && (
            <span className="inline-flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
              <Bot aria-hidden className="size-3.5" />
              from AI run #{r.run_id}
            </span>
          )}
        </div>
      ),
    },
    { id: 'exam', header: 'Exam', cell: (r) => r.exam_name ?? '-' },
    { id: 'scope', header: 'Scope', cell: (r) => r.scope_label },
    {
      id: 'format',
      header: 'Format',
      cell: (r) => {
        const Icon = r.format === 'pdf' ? FileText : FileSpreadsheet
        return (
          <span className="inline-flex items-center gap-1.5">
            <Icon
              aria-hidden
              className={r.format === 'pdf' ? 'size-4 text-rose-500' : 'size-4 text-emerald-600'}
            />
            <span>{r.format === 'pdf' ? 'PDF' : 'Excel'}</span>
            {r.size_bytes !== null && (
              <span className="text-xs text-slate-400">{formatSize(r.size_bytes)}</span>
            )}
          </span>
        )
      },
    },
    {
      id: 'created',
      header: 'Created',
      cell: (r) => (
        <div className="flex flex-col">
          <span>{formatCreatedAt(r.created_at)}</span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {r.created_by_name ?? (r.run_id !== null ? 'Reporting Agent' : 'Unknown')}
          </span>
        </div>
      ),
    },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      cell: (r) => (
        <div className="flex items-center justify-end gap-2">
          <GradientButton
            size="sm"
            variant="secondary"
            icon={Download}
            loading={downloadingId === r.id}
            onClick={() => onDownload(r)}
            aria-label={`Download ${REPORT_KIND_LABELS[r.kind]} report #${r.id}`}
          >
            Download
          </GradientButton>
          {canDelete && (
            <GradientButton
              size="sm"
              variant="ghost"
              icon={Trash2}
              loading={deletingId === r.id}
              onClick={() => onDelete(r)}
              aria-label={`Delete report #${r.id}`}
            />
          )}
        </div>
      ),
    },
  ]

  return (
    <DataTable
      columns={columns}
      rows={reports}
      getRowId={(r) => r.id}
      loading={loading}
      caption="Generated reports"
      empty={
        <EmptyState
          icon={FileText}
          title="No reports yet"
          description="Generate a principal, class teacher or subject teacher report - or start an agent run, which produces the principal report automatically."
        />
      }
    />
  )
}
