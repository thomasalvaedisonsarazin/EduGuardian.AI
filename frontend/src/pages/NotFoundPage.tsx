import { ArrowLeft, Compass } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { EmptyState } from '@/components/ui/EmptyState'
import { GlassCard } from '@/components/ui/GlassCard'
import { GradientButton } from '@/components/ui/GradientButton'

export default function NotFoundPage() {
  const navigate = useNavigate()
  return (
    <PageWrapper title="Page not found">
      <GlassCard hoverable={false}>
        <EmptyState
          icon={Compass}
          title="We could not find that page"
          description="The link may be outdated, or the resource belongs to another school."
          action={
            <GradientButton icon={ArrowLeft} onClick={() => navigate('/dashboard')}>
              Back to dashboard
            </GradientButton>
          }
        />
      </GlassCard>
    </PageWrapper>
  )
}
