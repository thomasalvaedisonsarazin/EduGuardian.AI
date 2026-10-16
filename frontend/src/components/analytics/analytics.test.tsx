import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { RiskReason, StudentResult, SubjectConfig } from '@/types/analytics'
import { DeltaValue, RiskReasonBadges, StatTile, StudentResultsTable, fmtDelta, fmtPct } from '.'

const reasons: RiskReason[] = [
  { code: 'FAILED_SUBJECTS', detail: 'Failed 2 subjects: Maths, Science', evidence: { count: 2 } },
  { code: 'SHARP_DROP', detail: 'Dropped 20.00 points vs previous exam', evidence: { delta: '-20.00' } },
  { code: 'LOW_OVERALL', detail: 'Overall 20.00% is below 40%', evidence: { percentage: '20.00' } },
]

const subjects: SubjectConfig[] = [{ subject_id: 1, name: 'Maths', max_marks: '100.00', pass_marks: '35.00' }]

function result(id: number, name: string, pct: string, rank: number, marks: string): StudentResult {
  const passed = Number(marks) >= 35
  return {
    student_id: id,
    pseudo_id: `S-000${id}`,
    full_name: name,
    class_section_id: 1,
    class_label: '8-A',
    subjects: [
      {
        subject_id: 1,
        subject_name: 'Maths',
        marks,
        max_marks: '100.00',
        pass_marks: '35.00',
        is_absent: false,
        is_missing: false,
        passed,
        percentage: pct,
      },
    ],
    total: marks,
    max_total: '100.00',
    percentage: pct,
    passed,
    appeared: true,
    failed_subjects: passed ? [] : [1],
    rank_in_section: rank,
    section_size: 3,
  }
}

describe('analytics components', () => {
  it('RiskReasonBadges renders a labelled badge per reason with detail titles', () => {
    render(<RiskReasonBadges reasons={reasons} />)
    const list = screen.getByRole('list', { name: 'Risk reasons' })
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(screen.getByText('Failed subjects')).toBeInTheDocument()
    expect(screen.getByText('Sharp drop')).toBeInTheDocument()
    expect(screen.getByText('Below 40%')).toBeInTheDocument()
    expect(items[1]).toHaveAttribute('title', 'Dropped 20.00 points vs previous exam')
  })

  it('RiskReasonBadges renders nothing without reasons', () => {
    const { container } = render(<RiskReasonBadges reasons={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('StatTile shows label, value and hint', () => {
    render(<StatTile label="Pass rate" value="50.0%" hint="3 of 6 passed" />)
    expect(screen.getByText('Pass rate')).toBeInTheDocument()
    expect(screen.getByText('50.0%')).toBeInTheDocument()
    expect(screen.getByText('3 of 6 passed')).toBeInTheDocument()
  })

  it('formats percentages and signed deltas', () => {
    expect(fmtPct('88.00')).toBe('88.0%')
    expect(fmtPct(null)).toBe('—')
    expect(fmtDelta('-20.00')).toBe('−20.0 pts')
    expect(fmtDelta('8')).toBe('+8.0 pts')
    render(<DeltaValue value="-7.20" />)
    expect(screen.getByText('−7.2 pts')).toBeInTheDocument()
  })

  it('StudentResultsTable sorts by percentage and shows the comparison column', async () => {
    render(
      <MemoryRouter>
        <StudentResultsTable
          results={[result(1, 'Asha', '88.00', 1, '88'), result(2, 'Bala', '20.00', 3, '20'), result(3, 'Chitra', '68.00', 2, '68')]}
          changes={[{ student_id: 2, previous_percentage: '40.00', current_percentage: '20.00', delta: '-20.00', subjects: [] }]}
          subjects={subjects}
          previousExamName="Unit Test 1"
        />
      </MemoryRouter>,
    )
    const names = () => screen.getAllByRole('link').map((a) => a.textContent)
    expect(names()).toEqual(['S-0001Asha', 'S-0003Chitra', 'S-0002Bala'])
    expect(screen.getByText('−20.0 pts')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sort by vs unit test 1/i })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /sort by %/i }))
    expect(names()).toEqual(['S-0001Asha', 'S-0003Chitra', 'S-0002Bala'])
    await userEvent.click(screen.getByRole('button', { name: /sort by %/i }))
    expect(names()).toEqual(['S-0002Bala', 'S-0003Chitra', 'S-0001Asha'])
    expect(screen.getByText('Fail')).toBeInTheDocument()
  })
})
