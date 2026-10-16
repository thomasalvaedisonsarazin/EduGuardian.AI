import type { ReactNode } from 'react'
import { GlassCard } from '@/components/ui/GlassCard'
import { TextReveal } from '@/components/ui/TextReveal'
import { Logo } from './Logo'
import { MeshBackground } from './MeshBackground'
import { PageWrapper } from './PageWrapper'

export interface AuthLayoutProps {
  title: string
  subtitle?: ReactNode
  footer?: ReactNode
  children: ReactNode
}

/** Centered card layout with mesh background for /login and /register. */
export function AuthLayout({ title, subtitle, footer, children }: AuthLayoutProps) {
  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-10">
      <MeshBackground />
      <PageWrapper className="max-w-md">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>
        <GlassCard hoverable={false} padding="lg">
          <TextReveal text={title} as="h1" className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white" />
          {subtitle && <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </GlassCard>
        {footer && <div className="mt-6 text-center text-sm text-slate-600 dark:text-slate-400">{footer}</div>}
      </PageWrapper>
    </div>
  )
}
