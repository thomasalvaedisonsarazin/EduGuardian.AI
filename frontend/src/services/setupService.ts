/** API calls for Module 2 (Academic Setup). All paths are relative to /api/v1. */
import api from '@/services/api'
import type { AcademicYear, Exam, ID, Student, Subject, Teacher, TeachingAssignment } from '@/types'
import type {
  AcademicYearInput,
  ClassSectionInput,
  ClassSectionWithCount,
  ExamInput,
  ExamSubjectConfigDetail,
  ExamSubjectConfigInput,
  StudentImportResult,
  StudentInput,
  StudentListParams,
  StudentListResponse,
  SubjectInput,
  TeacherInput,
  TeachingAssignmentInput,
} from '@/types/setup'

async function get<T>(url: string, params?: object): Promise<T> {
  const { data } = await api.get<T>(url, { params })
  return data
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const { data } = await api.post<T>(url, body)
  return data
}

async function patch<T>(url: string, body: unknown): Promise<T> {
  const { data } = await api.patch<T>(url, body)
  return data
}

async function remove(url: string): Promise<void> {
  await api.delete(url)
}

export const setupService = {
  // academic years
  listAcademicYears: () => get<AcademicYear[]>('/academic-years'),
  createAcademicYear: (input: AcademicYearInput) => post<AcademicYear>('/academic-years', input),
  updateAcademicYear: (id: ID, input: Partial<AcademicYearInput>) => patch<AcademicYear>(`/academic-years/${id}`, input),
  deleteAcademicYear: (id: ID) => remove(`/academic-years/${id}`),

  // classes
  listClasses: (academicYearId?: ID) =>
    get<ClassSectionWithCount[]>('/classes', academicYearId ? { academic_year_id: academicYearId } : undefined),
  createClass: (input: ClassSectionInput) => post<ClassSectionWithCount>('/classes', input),
  updateClass: (id: ID, input: Partial<ClassSectionInput>) => patch<ClassSectionWithCount>(`/classes/${id}`, input),
  deleteClass: (id: ID) => remove(`/classes/${id}`),

  // subjects
  listSubjects: () => get<Subject[]>('/subjects'),
  createSubject: (input: SubjectInput) => post<Subject>('/subjects', input),
  updateSubject: (id: ID, input: Partial<SubjectInput>) => patch<Subject>(`/subjects/${id}`, input),
  deleteSubject: (id: ID) => remove(`/subjects/${id}`),

  // teachers
  listTeachers: () => get<Teacher[]>('/teachers'),
  createTeacher: (input: TeacherInput) => post<Teacher>('/teachers', input),
  updateTeacher: (id: ID, input: Partial<TeacherInput>) => patch<Teacher>(`/teachers/${id}`, input),
  deleteTeacher: (id: ID) => remove(`/teachers/${id}`),

  // teaching assignments
  listTeachingAssignments: (params?: { teacher_id?: ID; class_section_id?: ID }) =>
    get<TeachingAssignment[]>('/teaching-assignments', params),
  createTeachingAssignment: (input: TeachingAssignmentInput) => post<TeachingAssignment>('/teaching-assignments', input),
  updateTeachingAssignment: (id: ID, input: Partial<TeachingAssignmentInput>) =>
    patch<TeachingAssignment>(`/teaching-assignments/${id}`, input),
  deleteTeachingAssignment: (id: ID) => remove(`/teaching-assignments/${id}`),

  // students
  listStudents: (params: StudentListParams = {}) => get<StudentListResponse>('/students', params),
  getStudent: (id: ID) => get<Student>(`/students/${id}`),
  createStudent: (input: StudentInput) => post<Student>('/students', input),
  updateStudent: (id: ID, input: Partial<StudentInput>) => patch<Student>(`/students/${id}`, input),
  deleteStudent: (id: ID) => remove(`/students/${id}`),
  importStudents: async (file: File): Promise<StudentImportResult> => {
    const form = new FormData()
    form.append('file', file)
    // No explicit Content-Type: the browser sets multipart/form-data with the boundary.
    const { data } = await api.post<StudentImportResult>('/students/import', form)
    return data
  },

  // exams
  listExams: (academicYearId?: ID) => get<Exam[]>('/exams', academicYearId ? { academic_year_id: academicYearId } : undefined),
  getExam: (id: ID) => get<Exam>(`/exams/${id}`),
  createExam: (input: ExamInput) => post<Exam>('/exams', input),
  updateExam: (id: ID, input: Partial<ExamInput>) => patch<Exam>(`/exams/${id}`, input),
  deleteExam: (id: ID) => remove(`/exams/${id}`),
  listExamSubjects: (examId: ID) => get<ExamSubjectConfigDetail[]>(`/exams/${examId}/subjects`),
  replaceExamSubjects: async (examId: ID, configs: ExamSubjectConfigInput[]): Promise<ExamSubjectConfigDetail[]> => {
    const { data } = await api.put<ExamSubjectConfigDetail[]>(`/exams/${examId}/subjects`, configs)
    return data
  },
}

export type SetupService = typeof setupService
