/**
 * Module 2 (Academic Setup) request/response types that extend the shared domain types.
 * Mirrors backend/app/schemas/setup.py.
 */
import type { ClassSection, DecimalValue, ExamSubjectConfig, ID, ISODate, Student } from '@/types'

export interface ClassSectionWithCount extends ClassSection {
  student_count: number
}

export interface ExamSubjectConfigDetail extends ExamSubjectConfig {
  subject_name: string
  subject_code: string
}

export interface StudentListResponse {
  items: Student[]
  total: number
}

export interface StudentListParams {
  class_section_id?: ID
  q?: string
  limit?: number
  offset?: number
}

export interface ImportRowError {
  row: number
  message: string
}

export interface StudentImportResult {
  created: number
  updated: number
  errors: ImportRowError[]
}

export interface AcademicYearInput {
  label: string
  is_current: boolean
}

export interface ClassSectionInput {
  academic_year_id: ID
  grade: number
  section: string
}

export interface SubjectInput {
  name: string
  code: string
}

export interface TeacherInput {
  full_name: string
  user_id?: ID | null
}

export interface TeachingAssignmentInput {
  teacher_id: ID
  class_section_id: ID
  subject_id: ID
  is_class_teacher: boolean
}

export interface StudentInput {
  class_section_id: ID
  admission_no: string
  full_name: string
}

export interface ExamInput {
  academic_year_id: ID
  name: string
  sequence: number
  held_on: ISODate | null
}

export interface ExamSubjectConfigInput {
  subject_id: ID
  max_marks: DecimalValue
  pass_marks: DecimalValue
}

export type SetupTab = 'years' | 'classes' | 'subjects' | 'teachers' | 'students' | 'exams'
