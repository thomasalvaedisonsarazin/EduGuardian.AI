import { QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { AppShell } from '@/components/layout/AppShell'
import { PageSpinner } from '@/components/ui/Spinner'
import { ThemeProvider } from '@/context/ThemeProvider'
import { queryClient } from '@/lib/queryClient'

const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const SetupPage = lazy(() => import('@/pages/SetupPage'))
const ImportMarksPage = lazy(() => import('@/pages/ImportMarksPage'))
const AnalyticsPage = lazy(() => import('@/pages/AnalyticsPage'))
const ExamAnalyticsPage = lazy(() => import('@/pages/ExamAnalyticsPage'))
const StudentPage = lazy(() => import('@/pages/StudentPage'))
const AgentsPage = lazy(() => import('@/pages/AgentsPage'))
const InterventionsPage = lazy(() => import('@/pages/InterventionsPage'))
const ReportsPage = lazy(() => import('@/pages/ReportsPage'))
const AuditPage = lazy(() => import('@/pages/AuditPage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

/** Route table (without providers/router) so tests can mount it in a MemoryRouter. */
export function AppRoutes() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/imports/new" element={<ImportMarksPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/analytics/exams/:examId" element={<ExamAnalyticsPage />} />
          <Route path="/students/:studentId" element={<StudentPage />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/interventions" element={<InterventionsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/audit" element={<AuditPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
