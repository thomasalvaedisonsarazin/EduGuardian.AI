/** Typed client for /api/v1/reports (+ the lookups the generate form needs). */
import api from '@/services/api'
import type { ClassSection, ID, Teacher } from '@/types'
import type { ExamListItem } from '@/types/analytics'
import type { ReportCreateInput, ReportItem, ReportListFilters } from '@/types/reports'

/** Extracts `filename="..."` from a Content-Disposition header. */
export function filenameFromDisposition(header: string | undefined, fallback: string): string {
  if (!header) return fallback
  const star = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(header)
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1].trim().replace(/^"|"$/g, ''))
    } catch {
      // fall through to the plain filename
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header)
  return plain?.[1]?.trim() || fallback
}

/** Saves a Blob through a temporary object URL + anchor click. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
}

export const reportService = {
  async list(filters: ReportListFilters = {}): Promise<ReportItem[]> {
    const { data } = await api.get<ReportItem[]>('/reports', { params: filters })
    return data
  },

  async create(input: ReportCreateInput): Promise<ReportItem> {
    // Report generation renders PDFs/workbooks synchronously - allow extra time.
    const { data } = await api.post<ReportItem>('/reports', input, { timeout: 120_000 })
    return data
  },

  async remove(id: ID): Promise<void> {
    await api.delete(`/reports/${id}`)
  },

  /** Downloads through the authenticated axios client (Bearer + X-School-Id headers). */
  async download(report: Pick<ReportItem, 'id' | 'file_name'>): Promise<void> {
    const response = await api.get<Blob>(`/reports/${report.id}/download`, { responseType: 'blob', timeout: 60_000 })
    const header = response.headers['content-disposition'] as string | undefined
    saveBlob(response.data, filenameFromDisposition(header, report.file_name))
  },

  async exams(): Promise<ExamListItem[]> {
    const { data } = await api.get<ExamListItem[]>('/analytics/exams')
    return data
  },

  async classes(): Promise<ClassSection[]> {
    const { data } = await api.get<ClassSection[]>('/classes')
    return data
  },

  async teachers(): Promise<Teacher[]> {
    const { data } = await api.get<Teacher[]>('/teachers')
    return data
  },
}
