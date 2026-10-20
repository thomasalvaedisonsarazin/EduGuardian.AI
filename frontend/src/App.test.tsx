import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppRoutes } from './App'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeProvider'
import { setTokens } from './lib/storage'
import { authService } from './services/authService'

vi.mock('./services/authService')

function renderAt(path: string) {
  return render(
    <ThemeProvider>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <AuthProvider>
          <MemoryRouter initialEntries={[path]}>
            <AppRoutes />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>,
  )
}

function signIn() {
  setTokens({ access_token: 'acc' })
}

beforeEach(() => {
  vi.mocked(authService.getMe).mockResolvedValue({
    id: 1,
    email: 'a@school.edu',
    full_name: 'Asha Rao',
    is_active: true,
    is_superadmin: false,
    created_at: '2026-01-01T00:00:00Z',
    memberships: [
      {
        id: 1,
        user_id: 1,
        school_id: 1,
        role: 'school_admin',
        school: { id: 1, name: 'Green Valley High', code: 'GVH', created_at: '2026-01-01T00:00:00Z' },
      },
    ],
  })
})

afterEach(() => {
  window.localStorage.clear()
  vi.clearAllMocks()
})

describe('routing', () => {
  it('renders the app shell with navigation on /dashboard', async () => {
    signIn()
    renderAt('/dashboard')
    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' }, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /audit log/i }).length).toBeGreaterThan(0)
    expect(screen.getByText('Green Valley High')).toBeInTheDocument()
  })

  it('redirects / to /dashboard', async () => {
    signIn()
    renderAt('/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' }, { timeout: 5000 })).toBeInTheDocument()
  })

  it('redirects signed-out users to /login', async () => {
    renderAt('/dashboard')
    expect(await screen.findByRole('button', { name: /sign in/i })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: /main navigation/i })).not.toBeInTheDocument()
  })

  it('renders the login page without the shell', async () => {
    renderAt('/login')
    expect(await screen.findByRole('button', { name: /sign in/i })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: /main navigation/i })).not.toBeInTheDocument()
  })

  it('shows not found for unknown routes', async () => {
    signIn()
    renderAt('/nope')
    expect(await screen.findByText('Page not found')).toBeInTheDocument()
  })
})
