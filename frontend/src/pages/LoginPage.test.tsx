import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/context/AuthContext'
import { getAccessToken, getActiveSchoolId } from '@/lib/storage'
import { ApiError } from '@/services/api'
import { authService } from '@/services/authService'
import type { AuthUser } from '@/types/auth'
import LoginPage from './LoginPage'

vi.mock('@/services/authService')

const ME: AuthUser = {
  id: 1,
  email: 'asha@school.edu',
  full_name: 'Asha Rao',
  is_active: true,
  is_superadmin: false,
  created_at: '2026-01-01T00:00:00Z',
  memberships: [
    {
      id: 10,
      user_id: 1,
      school_id: 7,
      role: 'school_admin',
      school: { id: 7, name: 'Green Valley High', code: 'GVH', created_at: '2026-01-01T00:00:00Z' },
    },
  ],
}

function renderLogin(path = '/login') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/dashboard" element={<p>Dashboard target</p>} />
            <Route path="/analytics" element={<p>Analytics target</p>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(authService.getMe).mockResolvedValue(ME)
})

afterEach(() => {
  window.localStorage.clear()
  vi.clearAllMocks()
})

describe('LoginPage', () => {
  it('validates required fields without calling the API', async () => {
    renderLogin()
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(screen.getByText('Email is required')).toBeInTheDocument()
    expect(screen.getByText('Password is required')).toBeInTheDocument()
    expect(authService.login).not.toHaveBeenCalled()
  })

  it('rejects an invalid email', async () => {
    renderLogin()
    await userEvent.type(screen.getByLabelText('Email'), 'not-an-email')
    await userEvent.type(screen.getByLabelText('Password'), 'whatever')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(screen.getByText('Enter a valid email address')).toBeInTheDocument()
    expect(authService.login).not.toHaveBeenCalled()
  })

  it('logs in, stores the session and redirects to `next`', async () => {
    vi.mocked(authService.login).mockResolvedValue({
      access_token: 'acc',
      refresh_token: 'ref',
      token_type: 'bearer',
    })
    renderLogin('/login?next=%2Fanalytics')
    await userEvent.type(screen.getByLabelText('Email'), 'asha@school.edu')
    await userEvent.type(screen.getByLabelText('Password'), 'correct-horse')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText('Analytics target')).toBeInTheDocument()
    expect(authService.login).toHaveBeenCalledWith({ email: 'asha@school.edu', password: 'correct-horse' })
    expect(getAccessToken()).toBe('acc')
    expect(getActiveSchoolId()).toBe(7)
  })

  it('falls back to /dashboard for unsafe `next` values', async () => {
    vi.mocked(authService.login).mockResolvedValue({
      access_token: 'acc',
      refresh_token: 'ref',
      token_type: 'bearer',
    })
    renderLogin('/login?next=%2F%2Fevil.example.com')
    await userEvent.type(screen.getByLabelText('Email'), 'asha@school.edu')
    await userEvent.type(screen.getByLabelText('Password'), 'pw')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText('Dashboard target')).toBeInTheDocument()
  })

  it('shows the server error message on failure', async () => {
    vi.mocked(authService.login).mockRejectedValue(new ApiError('Invalid email or password', 'UNAUTHORIZED', 401))
    renderLogin()
    await userEvent.type(screen.getByLabelText('Email'), 'asha@school.edu')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password')
    await waitFor(() => expect(screen.getByRole('button', { name: /sign in/i })).toBeEnabled())
    expect(getAccessToken()).toBeNull()
  })
})
