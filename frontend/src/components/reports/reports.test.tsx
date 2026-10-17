import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { filenameFromDisposition } from '@/services/reportService'
import type { ClassSection, Teacher } from '@/types'
import type { ExamListItem } from '@/types/analytics'
import type { ReportCreateInput, ReportItem } from '@/types/reports'
import { GenerateReportForm } from './GenerateReportForm'
import { ReportList } from './ReportList'
import { INITIAL_REPORT_FORM, allowedKinds, toReportInput, validateReportForm } from './validation'

const exams: ExamListItem[] = [
  {
    exam: { id: 1, name: 'Unit Test 1', sequence: 1, held_on: null, academic_year_id: 1, academic_year_label: '2026-27' },
    mark_count: 10,
    has_marks: true,
  },
  {
    exam: { id: 2, name: 'Quarterly Exam', sequence: 2, held_on: null, academic_year_id: 1, academic_year_label: '2026-27' },
    mark_count: 10,
    has_marks: true,
  },
]
const classes: ClassSection[] = [
  { id: 11, school_id: 1, academic_year_id: 1, grade: 10, section: 'B' },
  { id: 10, school_id: 1, academic_year_id: 1, grade: 10, section: 'A' },
]
const teachers: Teacher[] = [{ id: 5, school_id: 1, user_id: null, full_name: 'Ms. Rao' }]

describe('report form validation', () => {
  it('requires an exam and the scope field for the chosen kind', () => {
    expect(validateReportForm(INITIAL_REPORT_FORM)).toEqual({ examId: 'Choose an exam.' })
    expect(validateReportForm({ ...INITIAL_REPORT_FORM, kind: 'class_teacher', examId: '2' })).toEqual({
      classSectionId: 'Choose a class.',
    })
    expect(validateReportForm({ ...INITIAL_REPORT_FORM, kind: 'subject_teacher', examId: '2' })).toEqual({
      teacherId: 'Choose a teacher.',
    })
    expect(validateReportForm({ ...INITIAL_REPORT_FORM, examId: 'abc' }).examId).toBeDefined()
  })

  it('blocks principal reports for teachers', () => {
    expect(allowedKinds('teacher')).toEqual(['class_teacher', 'subject_teacher'])
    expect(validateReportForm({ ...INITIAL_REPORT_FORM, examId: '2' }, 'teacher').kind).toBeDefined()
    expect(validateReportForm({ ...INITIAL_REPORT_FORM, examId: '2' }, 'principal')).toEqual({})
  })

  it('builds a body with only the relevant scope field', () => {
    expect(
      toReportInput({ kind: 'class_teacher', format: 'xlsx', examId: '2', classSectionId: '10', teacherId: '5' }),
    ).toEqual({ kind: 'class_teacher', format: 'xlsx', exam_id: 2, class_section_id: 10 })
    expect(toReportInput({ ...INITIAL_REPORT_FORM, kind: 'subject_teacher', examId: '2' })).toBeNull()
  })
})

describe('GenerateReportForm', () => {
  it('defaults to the latest exam and submits a principal PDF', async () => {
    const onSubmit = vi.fn<(input: ReportCreateInput) => void>()
    render(<GenerateReportForm exams={exams} classes={classes} teachers={teachers} userRole="school_admin" onSubmit={onSubmit} />)
    expect(screen.getByLabelText('Exam')).toHaveValue('2')
    await userEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    expect(onSubmit).toHaveBeenCalledWith({ kind: 'principal', format: 'pdf', exam_id: 2 })
  })

  it('shows the class select for class teacher reports and validates it', async () => {
    const onSubmit = vi.fn<(input: ReportCreateInput) => void>()
    render(<GenerateReportForm exams={exams} classes={classes} teachers={teachers} userRole="principal" onSubmit={onSubmit} />)
    expect(screen.queryByLabelText('Class')).not.toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Report type'), 'class_teacher')
    const classSelect = screen.getByLabelText('Class')
    expect([...(classSelect as HTMLSelectElement).options].map((o) => o.text)).toEqual(['Select a class', '10-A', '10-B'])
    expect(screen.queryByLabelText('Teacher')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText('Choose a class.')).toBeInTheDocument()

    await userEvent.selectOptions(classSelect, '11')
    expect(screen.queryByText('Choose a class.')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name: 'Excel' }))
    await userEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    expect(onSubmit).toHaveBeenCalledWith({ kind: 'class_teacher', format: 'xlsx', exam_id: 2, class_section_id: 11 })
  })

  it('offers teachers only their report types and a teacher select', async () => {
    const onSubmit = vi.fn<(input: ReportCreateInput) => void>()
    render(<GenerateReportForm exams={exams} classes={classes} teachers={teachers} userRole="teacher" onSubmit={onSubmit} />)
    const kind = screen.getByLabelText('Report type') as HTMLSelectElement
    expect([...kind.options].map((o) => o.value)).toEqual(['class_teacher', 'subject_teacher'])
    await userEvent.selectOptions(kind, 'subject_teacher')
    await userEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    expect(screen.getByText('Choose a teacher.')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Teacher'), '5')
    await userEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    expect(onSubmit).toHaveBeenCalledWith({ kind: 'subject_teacher', format: 'pdf', exam_id: 2, teacher_id: 5 })
  })
})

describe('ReportList', () => {
  const report: ReportItem = {
    id: 7,
    school_id: 1,
    run_id: 3,
    kind: 'principal',
    format: 'xlsx',
    exam_id: 2,
    exam_name: 'Quarterly Exam',
    class_section_id: null,
    teacher_id: null,
    scope_label: 'Whole school',
    file_name: '7_principal_quarterly-exam.xlsx',
    size_bytes: 20480,
    created_by: null,
    created_by_name: null,
    created_at: '2026-10-16T09:30:00Z',
    download_url: '/api/v1/reports/7/download',
  }

  it('renders rows with run provenance and admin-only delete', async () => {
    const onDownload = vi.fn<(r: ReportItem) => void>()
    const { rerender } = render(
      <ReportList reports={[report]} canDelete={false} onDownload={onDownload} onDelete={vi.fn<(r: ReportItem) => void>()} />,
    )
    expect(screen.getByText('from AI run #3')).toBeInTheDocument()
    expect(screen.getByText('Reporting Agent')).toBeInTheDocument()
    expect(screen.getByText('Excel')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete report #7' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Download Principal report #7' }))
    expect(onDownload).toHaveBeenCalledWith(report)

    rerender(<ReportList reports={[report]} canDelete onDownload={onDownload} onDelete={vi.fn<(r: ReportItem) => void>()} />)
    expect(screen.getByRole('button', { name: 'Delete report #7' })).toBeInTheDocument()
  })

  it('shows an empty state', () => {
    render(<ReportList reports={[]} canDelete={false} onDownload={vi.fn<(r: ReportItem) => void>()} onDelete={vi.fn<(r: ReportItem) => void>()} />)
    expect(screen.getByText('No reports yet')).toBeInTheDocument()
  })
})

describe('filenameFromDisposition', () => {
  it('parses plain and RFC 5987 filenames', () => {
    expect(filenameFromDisposition('attachment; filename="a b.pdf"', 'x')).toBe('a b.pdf')
    expect(filenameFromDisposition("attachment; filename*=utf-8''r%C3%A9port.xlsx", 'x')).toBe('réport.xlsx')
    expect(filenameFromDisposition(undefined, 'fallback.pdf')).toBe('fallback.pdf')
  })
})
