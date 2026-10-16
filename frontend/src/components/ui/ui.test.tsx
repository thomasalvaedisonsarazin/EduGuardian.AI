import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AnimatedInput, AnimatedList, Badge, DataTable, EmptyState, GradientButton, type DataTableColumn } from '.'

interface Row {
  id: number
  name: string
  score: number
}

const columns: DataTableColumn<Row>[] = [
  { id: 'name', header: 'Name', cell: (r) => r.name },
  { id: 'score', header: 'Score', cell: (r) => r.score, align: 'right' },
]

describe('UI kit', () => {
  it('GradientButton fires onClick and disables while loading', async () => {
    const onClick = vi.fn<() => void>()
    const { rerender } = render(<GradientButton onClick={onClick}>Save</GradientButton>)
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onClick).toHaveBeenCalledOnce()

    rerender(
      <GradientButton onClick={onClick} loading>
        Save
      </GradientButton>,
    )
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled()
  })

  it('AnimatedInput links label and error', () => {
    render(<AnimatedInput label="Email" error="Required" />)
    const input = screen.getByLabelText('Email')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('Required')).toBeInTheDocument()
  })

  it('DataTable renders rows and an empty state', () => {
    const { rerender } = render(
      <DataTable columns={columns} rows={[{ id: 1, name: 'S-0001', score: 88 }]} getRowId={(r) => r.id} />,
    )
    expect(screen.getByText('S-0001')).toBeInTheDocument()
    expect(screen.getByText('88')).toBeInTheDocument()

    rerender(<DataTable columns={columns} rows={[]} getRowId={(r) => r.id} empty={<EmptyState title="No students" />} />)
    expect(screen.getByText('No students')).toBeInTheDocument()
  })

  it('AnimatedList and Badge render content', () => {
    render(
      <AnimatedList
        items={['a', 'b']}
        getKey={(x) => x}
        renderItem={(x) => <Badge tone="brand">{x.toUpperCase()}</Badge>}
      />,
    )
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('B')).toBeInTheDocument()
  })
})
