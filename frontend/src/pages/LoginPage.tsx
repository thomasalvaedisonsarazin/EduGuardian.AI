import { LogIn, Lock, Mail } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { FormAlert } from '@/components/auth/FormAlert'
import { fieldErrorsFromApi, isValidEmail, safeNextPath, type FieldErrors } from '@/components/auth/formErrors'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { AnimatedInput } from '@/components/ui/AnimatedInput'
import { GradientButton } from '@/components/ui/GradientButton'
import { useAuth } from '@/hooks/useAuth'
import { getErrorMessage } from '@/services/api'

type Field = 'email' | 'password'
const FIELDS: readonly Field[] = ['email', 'password']

function validate(email: string, password: string): FieldErrors<Field> {
  const errors: FieldErrors<Field> = {}
  if (!email.trim()) errors.email = 'Email is required'
  else if (!isValidEmail(email)) errors.email = 'Enter a valid email address'
  if (!password) errors.password = 'Password is required'
  return errors
}

export default function LoginPage() {
  const { login, status } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNextPath(params.get('next'))

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<FieldErrors<Field>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (status === 'authenticated' && !submitting) return <Navigate to={next} replace />

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setFormError(null)
    const found = validate(email, password)
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setSubmitting(true)
    try {
      await login({ email: email.trim(), password })
      navigate(next, { replace: true })
    } catch (err) {
      setErrors(fieldErrorsFromApi(err, FIELDS))
      setFormError(getErrorMessage(err))
      setSubmitting(false)
    }
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
        <FormAlert message={formError} />
        <AnimatedInput
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          icon={Mail}
          placeholder="you@school.edu"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.email}
        />
        <AnimatedInput
          label="Password"
          type="password"
          name="password"
          autoComplete="current-password"
          icon={Lock}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={errors.password}
        />
        <GradientButton type="submit" icon={LogIn} fullWidth size="lg" loading={submitting}>
          Sign in
        </GradientButton>
      </form>
    </AuthLayout>
  )
}
