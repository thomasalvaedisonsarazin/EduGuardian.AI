import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setupService, type SetupService } from '@/services/setupService'
import type { AcademicYear, Exam, Student, Subject } from '@/types'
import type { ClassSectionWithCount, ExamSubjectConfigDetail, StudentImportResult } from '@/types/setup'
import SetupPage from './SetupPage'

vi.mock('@/services/setupService', () => ({
  setupService: {
    listAcademicYears: vi.fn<SetupService['listAcademicYears']>(),
    createAcademicYear: vi.fn<SetupService['createAcademicYear']>(),
    updateAcademicYear: vi.fn<SetupService['updateAcademicYear']>(),
    deleteAcademicYear: vi.fn<SetupService['deleteAcademicYear']>(),
    listClasses: vi.fn<SetupService['listClasses']>(),
    listSubjects: vi.fn<SetupService['listSubjects']>(),
    listStudents: vi.fn<SetupService['listStudents']>(),
    importStudents: vi.fn<SetupService['importStudents']>(),
    listExams: vi.fn<SetupService['listExams']>(),
    listExamSubjects: vi.fn<SetupService['listExamSubjects']>(),
    replaceExamSubjects: vi.fn<SetupService['replaceExamSubjects']>(),
  },
}))

const svc = vi.mocked(setupService)

const years: AcademicYear[] = [
  { id: 1, school_id: 1, label: '2026-27', is_current: true },
  { id: 2, school_id: 1, label: '2025-26', is_current: false },
]
const classes: ClassSectionWithCount[] = [
  { id: 10, school_id: 1, academic_year_id: 1, grade: 10, section: 'A', student_count: 2 },
]
const students: Student[] = [
  { id: 100, school_id: 1, class_section_id: 10, admission_no: 'GPS1001', full_name: 'Asha Rao', pseudo_id: 'S-0001' },
]
const subjects: Subject[] = [
  { id: 5, school_id: 1, name: 'Mathematics', code: 'MATH' },
  { id: 6, school_id: 1, name: 'English', code: 'ENG' },
]
const exams: Exam[] = [{ id: 7, school_id: 1, academic_year_id: 1, name: 'Unit Test 1', sequence: 1, held_on: null }]
const configs: ExamSubjectConfigDetail[] = [
  { id: 1, school_id: 1, exam_id: 7, subject_id: 5, subject_name: 'Mathematics', subject_code: 'MATH', max_marks: '100.00', pass_marks: '35.00' },
]

function renderPage(path = '/setup') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <SetupPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SetupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    svc.listAcademicYears.mockResolvedValue(years)
    svc.listClasses.mockResolvedValue(classes)
    svc.listSubjects.mockResolvedValue(subjects)
    svc.listStudents.mockResolvedValue({ items: students, total: 1 })
    svc.listExams.mockResolvedValue(exams)
    svc.listExamSubjects.mockResolvedValue(configs)
    svc.deleteAcademicYear.mockResolvedValue(undefined)
  })

  it('renders the academic years tab with the current badge', async () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'Academic Setup' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /academic years/i })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByText('2026-27')).toBeInTheDocument()
    expect(screen.getByText('Current')).toBeInTheDocument()
  })

  it('confirms deletes inline before calling the API', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Delete 2025-26' }))
    expect(svc.deleteAcademicYear).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    await waitFor(() => expect(svc.deleteAcademicYear).toHaveBeenCalledWith(2))
  })

  it('creates an academic year through the modal form', async () => {
    svc.createAcademicYear.mockResolvedValue({ id: 3, school_id: 1, label: '2027-28', is_current: false })
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /add year/i }))
    const dialog = screen.getByRole('dialog', { name: 'Add academic year' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    expect(within(dialog).getByText('Label is required')).toBeInTheDocument()
    await userEvent.type(within(dialog).getByLabelText('Label'), '2027-28')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(svc.createAcademicYear).toHaveBeenCalledWith({ label: '2027-28', is_current: false }))
  })

  it('lists students and shows an import summary', async () => {
    const result: StudentImportResult = { created: 3, updated: 1, errors: [{ row: 4, message: 'class 10-Z does not exist' }] }
    svc.importStudents.mockResolvedValue(result)
    renderPage('/setup?tab=students')
    expect(await screen.findByText('Asha Rao')).toBeInTheDocument()
    expect(screen.getByText('S-0001')).toBeInTheDocument()

    const file = new File(['admission_no,full_name,grade,section\n'], 'students.csv', { type: 'text/csv' })
    await userEvent.upload(screen.getByLabelText('Student file'), file)
    await userEvent.click(screen.getByRole('button', { name: /^import$/i }))
    expect(await screen.findByText('3 created')).toBeInTheDocument()
    expect(screen.getByText('1 updated')).toBeInTheDocument()
    expect(screen.getByText(/Row 4: class 10-Z does not exist/)).toBeInTheDocument()
  })

  it('validates exam subject configs (pass must not exceed max)', async () => {
    svc.replaceExamSubjects.mockResolvedValue(configs)
    renderPage('/setup?tab=exams')
    await userEvent.click(await screen.findByRole('button', { name: /subjects/i }))
    const pass = await screen.findByLabelText('Mathematics pass marks')
    await userEvent.clear(pass)
    await userEvent.type(pass, '150')
    expect(screen.getByText('Pass marks cannot exceed max marks')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save subjects/i })).toBeDisabled()

    await userEvent.clear(pass)
    await userEvent.type(pass, '40')
    await userEvent.click(screen.getByRole('button', { name: /save subjects/i }))
    await waitFor(() =>
      expect(svc.replaceExamSubjects).toHaveBeenCalledWith(7, [{ subject_id: 5, max_marks: 100, pass_marks: 40 }]),
    )
  })
})
