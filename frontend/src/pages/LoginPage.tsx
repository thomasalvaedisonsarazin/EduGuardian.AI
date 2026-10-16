import { LogIn, Lock, Mail } from 'lucide-react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { AnimatedInput } from '@/components/ui/AnimatedInput'
import { GradientButton } from '@/components/ui/GradientButton'

/** Phase 1 placeholder. Module 1 wires this form to POST /auth/login via AuthContext. */
export default function LoginPage() {
  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to your school workspace."
      footer={
        <>
          New to EduGuardian?{' '}
          <Link to="/register" className="font-semibold text-brand-600 hover:underline dark:text-brand-400">
            Create a school account
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <AnimatedInput label="Email" type="email" name="email" autoComplete="email" icon={Mail} placeholder="you@school.edu" />
        <AnimatedInput label="Password" type="password" name="password" autoComplete="current-password" icon={Lock} />
        <GradientButton type="submit" icon={LogIn} fullWidth size="lg">
          Sign in
        </GradientButton>
        <p className="text-center text-xs text-slate-400">Authentication arrives in Phase 2.</p>
      </form>
    </AuthLayout>
  )
}
