import { useQuery } from '@tanstack/react-query'
import { useActiveSchoolId } from '@/hooks/useSession'
import { analyticsService } from '@/services/analyticsService'
import type { ID } from '@/types'

/** Query keys are namespaced by the active school so switching schools never shows stale data. */
export const analyticsKeys = {
  all: (schoolId: ID | null) => ['analytics', schoolId] as const,
  overview: (schoolId: ID | null) => ['analytics', schoolId, 'overview'] as const,
  exams: (schoolId: ID | null) => ['analytics', schoolId, 'exams'] as const,
  summary: (schoolId: ID | null, examId: ID) => ['analytics', schoolId, 'exam', examId, 'summary'] as const,
  class: (schoolId: ID | null, examId: ID, classId: ID) =>
    ['analytics', schoolId, 'exam', examId, 'class', classId] as const,
  trend: (schoolId: ID | null, studentId: ID) => ['analytics', schoolId, 'student', studentId] as const,
}

export function useDashboardOverview() {
  const schoolId = useActiveSchoolId()
  return useQuery({ queryKey: analyticsKeys.overview(schoolId), queryFn: () => analyticsService.overview() })
}

export function useExamList() {
  const schoolId = useActiveSchoolId()
  return useQuery({ queryKey: analyticsKeys.exams(schoolId), queryFn: () => analyticsService.listExams() })
}

export function useExamSummary(examId: ID | null) {
  const schoolId = useActiveSchoolId()
  return useQuery({
    queryKey: analyticsKeys.summary(schoolId, examId ?? 0),
    queryFn: () => analyticsService.examSummary(examId ?? 0),
    enabled: examId !== null,
  })
}

export function useExamClass(examId: ID | null, classId: ID | null) {
  const schoolId = useActiveSchoolId()
  return useQuery({
    queryKey: analyticsKeys.class(schoolId, examId ?? 0, classId ?? 0),
    queryFn: () => analyticsService.examClass(examId ?? 0, classId ?? 0),
    enabled: examId !== null && classId !== null,
  })
}

export function useStudentTrend(studentId: ID | null) {
  const schoolId = useActiveSchoolId()
  return useQuery({
    queryKey: analyticsKeys.trend(schoolId, studentId ?? 0),
    queryFn: () => analyticsService.studentTrend(studentId ?? 0),
    enabled: studentId !== null,
  })
}

/** Parses a positive integer route param; null when absent/invalid. */
export function parseId(raw: string | undefined): ID | null {
  if (!raw || !/^\d+$/.test(raw)) return null
  const n = Number(raw)
  return n > 0 ? n : null
}
