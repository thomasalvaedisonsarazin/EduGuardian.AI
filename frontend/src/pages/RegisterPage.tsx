import { Hash, Lock, Mail, School, UserPlus, UserRound } from 'lucide-react'
import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { FormAlert } from '@/components/auth/FormAlert'
import { fieldErrorsFromApi, isValidEmail, safeNextPath, type FieldErrors } from '@/components/auth/formErrors'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { AnimatedInput } from '@/components/ui/AnimatedInput'
import { GradientButton } from '@/components/ui/GradientButton'
import { useAuth } from '@/hooks/useAuth'
import { getErrorMessage } from '@/services/api'
import type { RegisterPayload } from '@/types/auth'

type Field = 'full_name' | 'email' | 'password' | 'school_name' | 'school_code'
const FIELDS: readonly Field[] = ['full_name', 'email', 'password', 'school_name', 'school_code']
const CODE_RE = /^[A-Za-z0-9_-]{2,50}$/

interface FormState {
  full_name: string
  email: string
  password: string
  school_name: string
  school_code: string
}

const EMPTY: FormState = { full_name: '', email: '', password: '', school_name: '', school_code: '' }

function validate(form: FormState): FieldErrors<Field> {
  const errors: FieldErrors<Field> = {}
  if (!form.full_name.trim()) errors.full_name = 'Full name is required'
  if (!form.email.trim()) errors.email = 'Email is required'
  else if (!isValidEmail(form.email)) errors.email = 'Enter a valid email address'
  if (!form.password) errors.password = 'Password is required'
  else if (form.password.length < 8) errors.password = 'Use at least 8 characters'
  if (form.school_name.trim().length < 2) errors.school_name = 'School name is required'
  if (form.school_code.trim() && !CODE_RE.test(form.school_code.trim())) {
    errors.school_code = '2-50 letters, numbers, - or _'
  }
  return errors
}

export default function RegisterPage() {
  const { register, status } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNextPath(params.get('next'))

  const [form, setForm] = useState<FormState>(EMPTY)
  const [errors, setErrors] = useState<FieldErrors<Field>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (status === 'authenticated' && !submitting) return <Navigate to={next} replace />

  const set = (field: Field) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setFormError(null)
    const found = validate(form)
    setErrors(found)
    if (Object.keys(found).length > 0) return

    const payload: RegisterPayload = {
      full_name: form.full_name.trim(),
      email: form.email.trim(),
      password: form.password,
      school_name: form.school_name.trim(),
    }
    if (form.school_code.trim()) payload.school_code = form.school_code.trim()

    setSubmitting(true)
    try {
      await register(payload)
      navigate(next, { replace: true })
    } catch (err) {
      setErrors(fieldErrorsFromApi(err, FIELDS))
      setFormError(getErrorMessage(err))
      setSubmitting(false)
    }
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
        <FormAlert message={formError} />
        <AnimatedInput
          label="Full name"
          name="full_name"
          autoComplete="name"
          icon={UserRound}
          value={form.full_name}
          onChange={set('full_name')}
          error={errors.full_name}
        />
        <AnimatedInput
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          icon={Mail}
          value={form.email}
          onChange={set('email')}
          error={errors.email}
        />
        <AnimatedInput
          label="Password"
          type="password"
          name="password"
          autoComplete="new-password"
          icon={Lock}
          hint="At least 8 characters"
          value={form.password}
          onChange={set('password')}
          error={errors.password}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <AnimatedInput
            label="School name"
            name="school_name"
            autoComplete="organization"
            icon={School}
            value={form.school_name}
            onChange={set('school_name')}
            error={errors.school_name}
          />
          <AnimatedInput
            label="School code"
            name="school_code"
            icon={Hash}
            hint="Optional - generated if empty"
            value={form.school_code}
            onChange={set('school_code')}
            error={errors.school_code}
          />
        </div>
        <GradientButton type="submit" icon={UserPlus} fullWidth size="lg" loading={submitting}>
          Create account
        </GradientButton>
      </form>
    </AuthLayout>
  )
}
