import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { AgentRunDetail, AgentStepDetail } from '@/types/agents'
import { AgentStepTimeline, RunStatusBanner, formatCost, formatDuration } from '.'

function step(id: number, agent: string, status: AgentStepDetail['status'], extra: Partial<AgentStepDetail> = {}): AgentStepDetail {
  return {
    id,
    run_id: 1,
    agent_name: agent,
    status,
    started_at: '2026-10-16T10:00:00Z',
    finished_at: status === 'running' ? null : '2026-10-16T10:00:01Z',
    duration_ms: status === 'running' ? null : 1200,
    input_summary: { exam_id: 2 },
    output_summary: null,
    error: null,
    ...extra,
  }
}

describe('AgentStepTimeline', () => {
  it('shows finished, running and waiting agents in pipeline order with key numbers', () => {
    render(
      <AgentStepTimeline
        runStatus="running"
        steps={[
          step(1, 'DataQualityAgent', 'done', {
            output_summary: { students: 80, marks_recorded: 790, completeness_pct: 98.8, missing: 4, warnings: [] },
          }),
          step(2, 'PerformanceAnalysisAgent', 'done', {
            output_summary: { pass_percentage: '72.50', mean_percentage: '61.20', at_risk_total: 18 },
          }),
          step(3, 'InterventionAgent', 'running'),
        ]}
      />,
    )
    const items = within(screen.getByRole('list', { name: 'Agent steps' })).getAllByRole('listitem', {
      name: /:/,
    })
    expect(items.map((li) => li.getAttribute('aria-label'))).toEqual([
      'Data Quality: Done',
      'Performance Analysis: Done',
      'Intervention Drafting: Running',
      'Reporting: Waiting',
      'Orchestrator: Waiting',
    ])
    const analysis = screen.getByRole('list', { name: 'Performance Analysis results' })
    expect(within(analysis).getByText('72.5%')).toBeInTheDocument()
    expect(within(analysis).getByText('18')).toBeInTheDocument()
    expect(screen.getAllByText('1.2 s')).toHaveLength(2)
  })

  it('expands readable details and shows step errors; skipped agents after a failure', async () => {
    const user = userEvent.setup()
    render(
      <AgentStepTimeline
        runStatus="failed"
        steps={[
          step(1, 'DataQualityAgent', 'failed', {
            error: 'No committed marks found for Quarterly Exam',
            output_summary: { issues: [{ code: 'MISSING_MARK', count: 3 }] },
          }),
        ]}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('No committed marks')
    expect(screen.getByRole('listitem', { name: 'Reporting: Skipped' })).toBeInTheDocument()
    const toggle = screen.getByRole('button', { name: 'Show details' })
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Issues')).toBeInTheDocument()
    expect(screen.getByText('MISSING_MARK')).toBeInTheDocument()
    expect(screen.getByText('Exam id')).toBeInTheDocument()
  })
})

describe('RunStatusBanner', () => {
  const run: AgentRunDetail = {
    id: 7,
    school_id: 1,
    kind: 'full_analysis',
    status: 'awaiting_approval',
    requested_by: 1,
    requested_by_email: 'demo@eduguardian.test',
    input: { exam_id: 2 },
    exam_id: 2,
    exam_name: 'Quarterly Exam',
    created_at: '2026-10-16T10:00:00Z',
    finished_at: '2026-10-16T10:00:05Z',
    token_usage: 0,
    cost_usd: '0.0000',
    error: null,
    llm_mode: 'template',
    plan_counts: { draft: 18 },
    steps: [],
    reports: [
      { id: 1, kind: 'principal', format: 'pdf', created_at: '2026-10-16T10:00:04Z' },
      { id: 2, kind: 'principal', format: 'xlsx', created_at: '2026-10-16T10:00:05Z' },
    ],
    warnings: ['4 expected mark(s) are missing; they count as not passed.'],
  }

  it('links to the review queue and reports and shows LLM mode, cost and warnings', () => {
    render(
      <MemoryRouter>
        <RunStatusBanner run={run} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Awaiting approval')).toBeInTheDocument()
    expect(screen.getByText('Template mode (no LLM)')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Review 18 draft plans/ })).toHaveAttribute('href', '/interventions?run_id=7')
    expect(screen.getByRole('link', { name: /2 reports/ })).toHaveAttribute('href', '/reports')
    expect(screen.getByRole('list', { name: 'Warnings' })).toHaveTextContent('4 expected mark(s)')
  })
})

describe('formatters', () => {
  it('formats durations and costs', () => {
    expect(formatDuration(850)).toBe('850 ms')
    expect(formatDuration(65_000)).toBe('1 min 5 s')
    expect(formatDuration(null)).toBe('—')
    expect(formatCost('0.0012')).toBe('$0.0012')
    expect(formatCost(1.5)).toBe('$1.50')
    expect(formatCost('0')).toBe('$0.00')
  })
})
