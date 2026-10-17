import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useActiveSchoolId } from '@/hooks/useSession'
import { reportService } from '@/services/reportService'
import type { ID } from '@/types'
import type { ReportCreateInput, ReportItem, ReportListFilters } from '@/types/reports'

/** Query keys are namespaced by the active school so switching schools never shows stale data. */
export const reportKeys = {
  all: (schoolId: ID | null) => ['reports', schoolId] as const,
  list: (schoolId: ID | null, filters: ReportListFilters) => ['reports', schoolId, 'list', filters] as const,
  lookups: (schoolId: ID | null, what: 'exams' | 'classes' | 'teachers') => ['reports', schoolId, 'lookup', what] as const,
}

export function useReportList(filters: ReportListFilters = {}) {
  const schoolId = useActiveSchoolId()
  return useQuery({ queryKey: reportKeys.list(schoolId, filters), queryFn: () => reportService.list(filters) })
}

export function useReportExams() {
  const schoolId = useActiveSchoolId()
  return useQuery({ queryKey: reportKeys.lookups(schoolId, 'exams'), queryFn: () => reportService.exams() })
}

export function useReportClasses() {
  const schoolId = useActiveSchoolId()
  return useQuery({ queryKey: reportKeys.lookups(schoolId, 'classes'), queryFn: () => reportService.classes() })
}

export function useReportTeachers() {
  const schoolId = useActiveSchoolId()
  return useQuery({ queryKey: reportKeys.lookups(schoolId, 'teachers'), queryFn: () => reportService.teachers() })
}

export function useGenerateReport() {
  const schoolId = useActiveSchoolId()
  const qc = useQueryClient()
  return useMutation<ReportItem, Error, ReportCreateInput>({
    mutationFn: (input) => reportService.create(input),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...reportKeys.all(schoolId), 'list'] })
    },
  })
}

export function useDeleteReport() {
  const schoolId = useActiveSchoolId()
  const qc = useQueryClient()
  return useMutation<void, Error, ID>({
    mutationFn: (id) => reportService.remove(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...reportKeys.all(schoolId), 'list'] })
    },
  })
}

export function useDownloadReport() {
  return useMutation<void, Error, Pick<ReportItem, 'id' | 'file_name'>>({
    mutationFn: (report) => reportService.download(report),
  })
}
