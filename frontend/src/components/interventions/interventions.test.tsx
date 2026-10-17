import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import InterventionsPage from '@/pages/InterventionsPage'
import { analyticsService } from '@/services/analyticsService'
import { interventionService, type InterventionService } from '@/services/interventionService'
import { setupService, type SetupService } from '@/services/setupService'
import type { InterventionItem, InterventionList } from '@/types/interventions'
import { InterventionCard, type InterventionCardProps } from '.'

function handlers() {
  return {
    onApprove: vi.fn<InterventionCardProps['onApprove']>(),
    onReject: vi.fn<InterventionCardProps['onReject']>(),
    onSave: vi.fn<InterventionCardProps['onSave']>(),
    onStatus: vi.fn<InterventionCardProps['onStatus']>(),
  }
}

vi.mock('@/services/interventionService', () => ({
  interventionService: {
    list: vi.fn<InterventionService['list']>(),
    get: vi.fn<InterventionService['get']>(),
    update: vi.fn<InterventionService['update']>(),
    approve: vi.fn<InterventionService['approve']>(),
    reject: vi.fn<InterventionService['reject']>(),
    setStatus: vi.fn<InterventionService['setStatus']>(),
  },
}))
vi.mock('@/services/setupService', () => ({
  setupService: { listClasses: vi.fn<SetupService['listClasses']>() },
}))
vi.mock('@/services/analyticsService', () => ({
  analyticsService: { listExams: vi.fn<(typeof analyticsService)['listExams']>() },
}))

const svc = vi.mocked(interventionService)

const item: InterventionItem = {
  id: 11,
  run_id: 7,
  student: {
    id: 100,
    full_name: 'Asha Rao',
    pseudo_id: 'S-0001',
    admission_no: 'GPS1001',
    class_section_id: 3,
    class_label: '10-B',
  },
  subject_id: null,
  subject_name: null,
  status: 'draft',
  severity: 'high',
  exam_id: 2,
  exam_name: 'Quarterly Exam',
  evidence: {
    percentage: '31.40',
    reasons: [
      {
        code: 'FAILED_SUBJECTS',
        detail: 'Failed 1 subject: Mathematics',
        evidence: {
          count: 1,
          subjects: [
            { subject_name: 'Mathematics', marks: '22.00', max_marks: '100.00', pass_marks: '35.00', is_absent: false },
          ],
        },
      },
      {
        code: 'SHARP_DROP',
        detail: 'Dropped 18 points',
        evidence: { previous_percentage: '49.40', current_percentage: '31.40', delta: '-18.00' },
      },
    ],
    draft: { mode: 'template', summary: 'Short-term support in Mathematics.', focus_areas: ['Maths'], rationale: 'r' },
  },
  plan_text: 'Short-term support in Mathematics.\n\nActivities: ...',
  activities: [
    { title: 'Targeted practice in Mathematics', description: 'Short practice sets.', frequency: '3 times a week', owner: 'student' },
  ],
  reassess_on: '2026-11-20',
  approved_by: null,
  approved_by_email: null,
  approved_at: null,
  created_at: '2026-10-16T10:00:00Z',
  updated_at: null,
  can_review: true,
}

function listOf(items: InterventionItem[]): InterventionList {
  return { items, total: items.length, counts: { draft: items.filter((i) => i.status === 'draft').length } }
}

function renderPage(path = '/interventions?run_id=7') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <InterventionsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('InterventionCard', () => {
  it('shows the student, evidence and plan', () => {
    render(
      <MemoryRouter>
        <InterventionCard item={item} {...handlers()} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Asha Rao' })).toHaveAttribute('href', '/students/100')
    const subjects = screen.getByRole('list', { name: 'Subjects below the pass mark' })
    expect(within(subjects).getByText('Mathematics')).toBeInTheDocument()
    expect(within(subjects).getByText(/22\/100/)).toBeInTheDocument()
    expect(screen.getByText('−18.0 pts')).toBeInTheDocument()
    expect(screen.getByText('Targeted practice in Mathematics')).toBeInTheDocument()
    expect(screen.getByText('Failed subjects')).toBeInTheDocument()
  })

  it('collects an optional reason before rejecting', async () => {
    const user = userEvent.setup()
    const onReject = vi.fn<InterventionCardProps['onReject']>()
    render(
      <MemoryRouter>
        <InterventionCard item={item} {...handlers()} onReject={onReject} />
      </MemoryRouter>,
    )
    await user.click(screen.getByRole('button', { name: 'Reject' }))
    await user.type(screen.getByLabelText(/Reason for rejecting/), 'Already supported')
    await user.click(screen.getByRole('button', { name: 'Confirm reject' }))
    expect(onReject).toHaveBeenCalledWith(11, 'Already supported')
  })

  it('hides review actions when the user cannot review the plan', () => {
    render(
      <MemoryRouter>
        <InterventionCard
          item={{ ...item, can_review: false }}
          {...handlers()}
        />
      </MemoryRouter>,
    )
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
  })
})

describe('InterventionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(setupService.listClasses).mockResolvedValue([])
    vi.mocked(analyticsService.listExams).mockResolvedValue([])
  })

  it('approves a draft through the service and refreshes the queue', async () => {
    const user = userEvent.setup()
    svc.list.mockResolvedValueOnce(listOf([item])).mockResolvedValue(listOf([]))
    svc.approve.mockResolvedValue({ ...item, status: 'approved', approved_by: 1 })
    renderPage()

    expect(await screen.findByText('Asha Rao')).toBeInTheDocument()
    expect(svc.list).toHaveBeenCalledWith({ status: 'draft', run_id: 7 })
    expect(screen.getByRole('tab', { name: /Draft/ })).toHaveAttribute('aria-selected', 'true')

    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(svc.approve).toHaveBeenCalledWith(11))
    expect(await screen.findByText('No draft plans')).toBeInTheDocument()
    expect(svc.list).toHaveBeenCalledTimes(2)
  })

  it('saves an edited plan', async () => {
    const user = userEvent.setup()
    svc.list.mockResolvedValue(listOf([item]))
    svc.update.mockResolvedValue(item)
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Edit' }))
    const text = screen.getByLabelText('Plan text')
    await user.clear(text)
    await user.type(text, 'New plan')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() =>
      expect(svc.update).toHaveBeenCalledWith(11, {
        plan_text: 'New plan',
        activities: item.activities,
        reassess_on: '2026-11-20',
      }),
    )
  })
})
