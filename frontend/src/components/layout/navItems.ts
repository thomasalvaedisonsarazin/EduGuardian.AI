import {
  Bot,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  LineChart,
  ScrollText,
  Settings2,
  Upload,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  label: string
  to: string
  icon: LucideIcon
}

export const NAV_ITEMS: readonly NavItem[] = [
  { label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard },
  { label: 'Setup', to: '/setup', icon: Settings2 },
  { label: 'Import Marks', to: '/imports/new', icon: Upload },
  { label: 'Analytics', to: '/analytics', icon: LineChart },
  { label: 'AI Agents', to: '/agents', icon: Bot },
  { label: 'Interventions', to: '/interventions', icon: ClipboardCheck },
  { label: 'Reports', to: '/reports', icon: FileText },
  { label: 'Audit Log', to: '/audit', icon: ScrollText },
]
