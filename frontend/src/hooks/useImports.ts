import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useActiveSchoolId } from '@/hooks/useSession'
import { importService } from '@/services/importService'
import type { ID } from '@/types'
import type { ColumnMap, ImportBatchDetail, UploadImportInput } from '@/types/imports'

/** Query keys are namespaced by the active school so switching schools never shows stale data. */
export const importKeys = {
  all: (schoolId: ID | null) => ['imports', schoolId] as const,
  list: (schoolId: ID | null, examId?: ID) => ['imports', schoolId, 'list', examId ?? 'all'] as const,
  detail: (schoolId: ID | null, id: ID) => ['imports', schoolId, 'detail', id] as const,
  exams: (schoolId: ID | null) => ['imports', schoolId, 'exams'] as const,
}

export function useImportExams() {
  const schoolId = useActiveSchoolId()
  return useQuery({ queryKey: importKeys.exams(schoolId), queryFn: () => importService.listExams() })
}

export function useImportList(examId?: ID) {
  const schoolId = useActiveSchoolId()
  return useQuery({ queryKey: importKeys.list(schoolId, examId), queryFn: () => importService.list(examId) })
}

export function useImportBatch(id: ID | null) {
  const schoolId = useActiveSchoolId()
  return useQuery({
    queryKey: importKeys.detail(schoolId, id ?? 0),
    queryFn: () => importService.get(id ?? 0),
    enabled: id !== null,
  })
}

function useStoreBatch() {
  const qc = useQueryClient()
  const schoolId = useActiveSchoolId()
  return (batch: ImportBatchDetail) => {
    qc.setQueryData(importKeys.detail(schoolId, batch.id), batch)
    void qc.invalidateQueries({ queryKey: [...importKeys.all(schoolId), 'list'] })
  }
}

export function useUploadImport() {
  const store = useStoreBatch()
  return useMutation({
    mutationFn: ({ examId, file }: UploadImportInput) => importService.upload(examId, file),
    onSuccess: store,
  })
}

export function useUpdateMapping(id: ID) {
  const store = useStoreBatch()
  return useMutation({
    mutationFn: (mapping: ColumnMap) => importService.updateMapping(id, mapping),
    onSuccess: store,
  })
}

export function useRejectImport(id: ID) {
  const store = useStoreBatch()
  return useMutation({ mutationFn: () => importService.reject(id), onSuccess: store })
}

export function useCommitImport(id: ID) {
  const qc = useQueryClient()
  const schoolId = useActiveSchoolId()
  return useMutation({
    mutationFn: () => importService.commit(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: importKeys.all(schoolId) })
      // Committed marks change every analytics view.
      void qc.invalidateQueries({ queryKey: ['analytics', schoolId] })
    },
  })
}
