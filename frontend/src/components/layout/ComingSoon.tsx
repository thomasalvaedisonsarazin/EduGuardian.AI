import { Sparkles, type LucideIcon } from 'lucide-react'
import { GlassCard } from '@/components/ui/GlassCard'
import { EmptyState } from '@/components/ui/EmptyState'
import { PageWrapper } from './PageWrapper'

export interface ComingSoonProps {
  title: string
  description?: string
  icon?: LucideIcon
}

/** Temporary page body used by Phase 1 placeholder routes. */
export function ComingSoon({ title, description, icon = Sparkles }: ComingSoonProps) {
  return (
    <PageWrapper title={title} description={description}>
      <GlassCard hoverable={false}>
        <EmptyState icon={icon} title="Coming in Phase 2" description="This module is being built. Check back soon." />
      </GlassCard>
    </PageWrapper>
  )
}
