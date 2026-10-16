import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { ImportBatchDetail, ValidationIssue } from '@/types/imports'
import { IssueSummary } from './IssueSummary'
import { IssueTable } from './IssueTable'
import { cellIssueIndex } from './labels'
import { PreviewTable } from './PreviewTable'

const issues: ValidationIssue[] = [
  { row: 1, column: 'Maths', code: 'MARK_ABOVE_MAX', severity: 'error', message: 'Mark 120 is above the maximum of 100' },
  { row: 1, column: 'Maths', code: 'MISSING_MARK', severity: 'warning', message: 'Mark is blank' },
  { row: 2, column: 'Science', code: 'ABSENT', severity: 'warning', message: 'Marked absent' },
  { row: null, column: null, code: 'STUDENT_NOT_IN_FILE', severity: 'warning', message: 'A004 missing' },
]

describe('IssueSummary', () => {
  it('shows severity counts, per-code badges and the summary text', () => {
    render(
      <IssueSummary
        summary={{ errors: 2, warnings: 1, by_code: { NON_NUMERIC: 2, ABSENT: 1 } }}
        rowCount={30}
        text="Checked 30 rows."
      />,
    )
    const region = screen.getByRole('region', { name: 'Validation summary' })
    expect(within(region).getByText('30 rows')).toBeInTheDocument()
    expect(within(region).getByText(/2 errors/)).toBeInTheDocument()
    expect(within(region).getByText(/1 warning$/)).toBeInTheDocument()
    const byType = within(region).getByRole('list', { name: 'Issues by type' })
    const items = within(byType).getAllByRole('listitem')
    expect(items.map((li) => li.textContent)).toEqual(['Not a number: 2', 'Absent: 1'])
    expect(screen.getByText('Checked 30 rows.')).toBeInTheDocument()
    expect(screen.queryByText('No issues found')).not.toBeInTheDocument()
  })

  it('celebrates a clean file', () => {
    render(<IssueSummary summary={{ errors: 0, warnings: 0, by_code: {} }} />)
    expect(screen.getByText('No issues found')).toBeInTheDocument()
    expect(screen.getByText(/0 errors/)).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })
})

describe('IssueTable', () => {
  it('filters by severity', async () => {
    render(<IssueTable issues={issues} />)
    expect(screen.getByText('Showing 4 of 4')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Severity'), 'error')
    expect(screen.getByText('Showing 1 of 4')).toBeInTheDocument()
    expect(screen.getByText('Mark 120 is above the maximum of 100')).toBeInTheDocument()
    expect(screen.queryByText('Marked absent')).not.toBeInTheDocument()
  })
})

describe('preview highlighting', () => {
  it('keeps the worst severity per cell', () => {
    const index = cellIssueIndex(issues)
    expect(index.get('1|Maths')).toBe('error')
    expect(index.get('2|Science')).toBe('warning')
    expect(index.size).toBe(2)
  })

  it('marks problem cells in the preview table', () => {
    const batch: ImportBatchDetail = {
      id: 1,
      exam_id: 1,
      exam_name: 'Unit Test 1',
      filename: 'marks.csv',
      status: 'validated',
      row_count: 2,
      summary: { errors: 1, warnings: 3, by_code: {} },
      created_at: '2026-10-16T10:00:00Z',
      column_map: { admission_column: 'Adm', subjects: { Maths: 1, Science: 2 } },
      headers: ['Adm', 'Maths', 'Science'],
      issues,
      summary_text: '',
      preview: [
        {
          row: 1,
          admission_no: 'A001',
          student_id: 1,
          marks: {
            Maths: { subject_id: 1, raw: '120', value: '120', is_absent: false },
            Science: { subject_id: 2, raw: '40', value: '40', is_absent: false },
          },
        },
        {
          row: 2,
          admission_no: 'A002',
          student_id: 2,
          marks: {
            Maths: { subject_id: 1, raw: '50', value: '50', is_absent: false },
            Science: { subject_id: 2, raw: 'AB', value: null, is_absent: true },
          },
        },
      ],
      can_commit: false,
      exam_subjects: [
        { id: 1, name: 'Mathematics', code: 'MATH', max_marks: '100', pass_marks: '35' },
        { id: 2, name: 'Science', code: 'SCI', max_marks: '50', pass_marks: '18' },
      ],
      uploaded_by: null,
    }
    render(<PreviewTable batch={batch} />)
    expect(screen.getByText('120')).toHaveAttribute('data-severity', 'error')
    expect(screen.getByText('AB')).toHaveAttribute('data-severity', 'warning')
    expect(screen.getByText('40')).not.toHaveAttribute('data-severity')
    expect(screen.getByText('Mathematics')).toBeInTheDocument()
  })
})
