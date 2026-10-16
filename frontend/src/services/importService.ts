/** Typed client for /api/v1/imports (marks import) plus the exam list it depends on. */
import api from '@/services/api'
import type { Exam, ID } from '@/types'
import type { ColumnMap, CommitResult, ImportBatchDetail, ImportBatchListItem } from '@/types/imports'

export const importService = {
  /** Exams come from the academic setup module (GET /exams). */
  async listExams(): Promise<Exam[]> {
    const { data } = await api.get<Exam[]>('/exams')
    return data
  },

  async list(examId?: ID): Promise<ImportBatchListItem[]> {
    const { data } = await api.get<ImportBatchListItem[]>('/imports', {
      params: examId !== undefined ? { exam_id: examId } : {},
    })
    return data
  },

  async get(id: ID): Promise<ImportBatchDetail> {
    const { data } = await api.get<ImportBatchDetail>(`/imports/${id}`)
    return data
  },

  async upload(examId: ID, file: File): Promise<ImportBatchDetail> {
    const form = new FormData()
    form.append('exam_id', String(examId))
    form.append('file', file)
    const { data } = await api.post<ImportBatchDetail>('/imports', form, { timeout: 120_000 })
    return data
  },

  async updateMapping(id: ID, mapping: ColumnMap): Promise<ImportBatchDetail> {
    const { data } = await api.put<ImportBatchDetail>(`/imports/${id}/mapping`, mapping)
    return data
  },

  async commit(id: ID): Promise<CommitResult> {
    const { data } = await api.post<CommitResult>(`/imports/${id}/commit`)
    return data
  },

  async reject(id: ID): Promise<ImportBatchDetail> {
    const { data } = await api.post<ImportBatchDetail>(`/imports/${id}/reject`)
    return data
  },

  /** Downloads the CSV template for an exam and triggers a browser save. */
  async downloadTemplate(examId: ID): Promise<void> {
    const response = await api.get<Blob>('/imports/template', { params: { exam_id: examId }, responseType: 'blob' })
    const disposition = String(response.headers['content-disposition'] ?? '')
    const match = /filename="?([^";]+)"?/.exec(disposition)
    const filename = match?.[1] ?? `marks_template_${examId}.csv`
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  },
}
