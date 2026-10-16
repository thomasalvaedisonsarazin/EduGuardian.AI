import { Hash, Lock, Mail, School, UserPlus, UserRound } from 'lucide-react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { AnimatedInput } from '@/components/ui/AnimatedInput'
import { GradientButton } from '@/components/ui/GradientButton'

/** Phase 1 placeholder. Module 1 wires this form to POST /auth/register (creates user + school). */
export default function RegisterPage() {
  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
  }

  return (
    <AuthLayout
      title="Create your school workspace"
      subtitle="You will be the school admin and can invite colleagues later."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-brand-600 hover:underline dark:text-brand-400">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <AnimatedInput label="Full name" name="full_name" autoComplete="name" icon={UserRound} />
        <AnimatedInput label="Email" type="email" name="email" autoComplete="email" icon={Mail} />
        <AnimatedInput label="Password" type="password" name="password" autoComplete="new-password" icon={Lock} />
        <div className="grid gap-4 sm:grid-cols-2">
          <AnimatedInput label="School name" name="school_name" icon={School} />
          <AnimatedInput label="School code" name="school_code" icon={Hash} hint="Unique short code" />
        </div>
        <GradientButton type="submit" icon={UserPlus} fullWidth size="lg">
          Create account
        </GradientButton>
        <p className="text-center text-xs text-slate-400">Registration arrives in Phase 2.</p>
      </form>
    </AuthLayout>
  )
}
