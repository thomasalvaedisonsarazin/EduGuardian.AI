import type { BadgeTone } from '@/components/ui'
import type { RiskCode, RiskSeverity } from '@/types/analytics'

export const RISK_LABELS: Record<RiskCode, string> = {
  FAILED_SUBJECTS: 'Failed subjects',
  SHARP_DROP: 'Sharp drop',
  LOW_OVERALL: 'Below 40%',
}

export const RISK_TONES: Record<RiskCode, BadgeTone> = {
  FAILED_SUBJECTS: 'danger',
  SHARP_DROP: 'warning',
  LOW_OVERALL: 'info',
}

export const SEVERITY_TONES: Record<RiskSeverity, BadgeTone> = {
  high: 'danger',
  medium: 'warning',
}
