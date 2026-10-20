import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/context/AuthContext'
import { setActiveSchoolId, setTokens } from '@/lib/storage'
import { authService } from '@/services/authService'
import type { Role } from '@/types'
import type { AuthUser } from '@/types/auth'
import { ProtectedRoute } from './ProtectedRoute'

vi.mock('@/services/authService')

function makeUser(role: Role, superadmin = false): AuthUser {
  return {
    id: 1,
    email: 't@school.edu',
    full_name: 'Tara Teacher',
    is_active: true,
    is_superadmin: superadmin,
    created_at: '2026-01-01T00:00:00Z',
    memberships: [
      {
        id: 3,
        user_id: 1,
        school_id: 5,
        role,
        school: { id: 5, name: 'Hill School', code: 'HILL', created_at: '2026-01-01T00:00:00Z' },
      },
    ],
  }
}

function LoginProbe() {
  const { search } = useLocation()
  return <p>Login page {search}</p>
}

function renderAt(path: string, roles?: readonly Role[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/login" element={<LoginProbe />} />
            <Route
              path="/secret"
              element={
                <ProtectedRoute roles={roles}>
                  <p>Secret content</p>
                </ProtectedRoute>
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

function signIn() {
  setTokens({ access_token: 'acc' })
  setActiveSchoolId(5)
}

afterEach(() => {
  window.localStorage.clear()
  vi.clearAllMocks()
})

describe('ProtectedRoute', () => {
  it('redirects to /login with the original path as `next` when signed out', async () => {
    renderAt('/secret?tab=2')
    expect(await screen.findByText(`Login page ?next=${encodeURIComponent('/secret?tab=2')}`)).toBeInTheDocument()
    expect(screen.queryByText('Secret content')).not.toBeInTheDocument()
    expect(authService.getMe).not.toHaveBeenCalled()
  })

  it('shows a spinner while the session loads', () => {
    signIn()
    vi.mocked(authService.getMe).mockReturnValue(new Promise<AuthUser>(() => {}))
    renderAt('/secret')
    expect(screen.getByText('Checking your session')).toBeInTheDocument()
    expect(screen.queryByText('Secret content')).not.toBeInTheDocument()
  })

  it('renders children for an authenticated user', async () => {
    signIn()
    vi.mocked(authService.getMe).mockResolvedValue(makeUser('teacher'))
    renderAt('/secret')
    expect(await screen.findByText('Secret content')).toBeInTheDocument()
  })

  it('enforces roles with a friendly no-access state', async () => {
    signIn()
    vi.mocked(authService.getMe).mockResolvedValue(makeUser('teacher'))
    renderAt('/secret', ['school_admin', 'principal'])
    expect(await screen.findByText("You don't have access to this page")).toBeInTheDocument()
    expect(screen.getByText(/School admin, Principal/)).toBeInTheDocument()
    expect(screen.queryByText('Secret content')).not.toBeInTheDocument()
  })

  it('allows matching roles and superadmins', async () => {
    signIn()
    vi.mocked(authService.getMe).mockResolvedValue(makeUser('teacher', true))
    renderAt('/secret', ['school_admin'])
    expect(await screen.findByText('Secret content')).toBeInTheDocument()
  })

  it('redirects to login when loading the profile fails', async () => {
    signIn()
    vi.mocked(authService.getMe).mockRejectedValue(new Error('boom'))
    renderAt('/secret')
    expect(await screen.findByText(/Login page/)).toBeInTheDocument()
  })
})
