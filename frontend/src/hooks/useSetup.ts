/** React Query hooks for Module 2 (Academic Setup). */
import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { useActiveSchoolId } from '@/hooks/useSession'
import { setupService } from '@/services/setupService'
import type { ID } from '@/types'
import type { ExamSubjectConfigInput, StudentListParams } from '@/types/setup'

/** Query keys are scoped by the active school so switching schools never shows stale data. */
export const setupKeys = {
  all: (schoolId: ID | null) => ['setup', schoolId] as const,
  years: (schoolId: ID | null) => ['setup', schoolId, 'years'] as const,
  classes: (schoolId: ID | null, yearId?: ID) => ['setup', schoolId, 'classes', yearId ?? 'all'] as const,
  subjects: (schoolId: ID | null) => ['setup', schoolId, 'subjects'] as const,
  teachers: (schoolId: ID | null) => ['setup', schoolId, 'teachers'] as const,
  assignments: (schoolId: ID | null, teacherId?: ID, classId?: ID) =>
    ['setup', schoolId, 'assignments', teacherId ?? 'all', classId ?? 'all'] as const,
  students: (schoolId: ID | null, params: StudentListParams) => ['setup', schoolId, 'students', params] as const,
  exams: (schoolId: ID | null, yearId?: ID) => ['setup', schoolId, 'exams', yearId ?? 'all'] as const,
  examSubjects: (schoolId: ID | null, examId: ID) => ['setup', schoolId, 'exam-subjects', examId] as const,
}

export function useAcademicYears() {
  const school = useActiveSchoolId()
  return useQuery({ queryKey: setupKeys.years(school), queryFn: setupService.listAcademicYears })
}

export function useClasses(academicYearId?: ID) {
  const school = useActiveSchoolId()
  return useQuery({
    queryKey: setupKeys.classes(school, academicYearId),
    queryFn: () => setupService.listClasses(academicYearId),
  })
}

export function useSubjects() {
  const school = useActiveSchoolId()
  return useQuery({ queryKey: setupKeys.subjects(school), queryFn: setupService.listSubjects })
}

export function useTeachers() {
  const school = useActiveSchoolId()
  return useQuery({ queryKey: setupKeys.teachers(school), queryFn: setupService.listTeachers })
}

export function useTeachingAssignments(params: { teacher_id?: ID; class_section_id?: ID } = {}) {
  const school = useActiveSchoolId()
  return useQuery({
    queryKey: setupKeys.assignments(school, params.teacher_id, params.class_section_id),
    queryFn: () => setupService.listTeachingAssignments(params),
  })
}

export function useStudents(params: StudentListParams) {
  const school = useActiveSchoolId()
  return useQuery({
    queryKey: setupKeys.students(school, params),
    queryFn: () => setupService.listStudents(params),
    placeholderData: keepPreviousData,
  })
}

export function useExams(academicYearId?: ID) {
  const school = useActiveSchoolId()
  return useQuery({
    queryKey: setupKeys.exams(school, academicYearId),
    queryFn: () => setupService.listExams(academicYearId),
  })
}

export function useExamSubjects(examId: ID | null) {
  const school = useActiveSchoolId()
  return useQuery({
    queryKey: setupKeys.examSubjects(school, examId ?? 0),
    queryFn: () => setupService.listExamSubjects(examId ?? 0),
    enabled: examId !== null,
  })
}

/**
 * Generic setup mutation: runs `fn` and invalidates every setup query for the active school
 * (lists are small; counts such as `student_count` depend on several entities).
 */
export function useSetupMutation<TVars, TResult>(fn: (vars: TVars) => Promise<TResult>) {
  const qc = useQueryClient()
  const school = useActiveSchoolId()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => qc.invalidateQueries({ queryKey: setupKeys.all(school) }),
  })
}

export function useImportStudents() {
  return useSetupMutation((file: File) => setupService.importStudents(file))
}

export function useReplaceExamSubjects(examId: ID) {
  return useSetupMutation((configs: ExamSubjectConfigInput[]) => setupService.replaceExamSubjects(examId, configs))
}
