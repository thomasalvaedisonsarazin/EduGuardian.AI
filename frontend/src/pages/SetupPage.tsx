import { motion } from 'framer-motion'
import { BookOpen, CalendarRange, ClipboardList, GraduationCap, School, Users, type LucideIcon } from 'lucide-react'
import { useRef, type KeyboardEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ClassesTab } from '@/components/setup/ClassesTab'
import { ExamsTab } from '@/components/setup/ExamsTab'
import { StudentsTab } from '@/components/setup/StudentsTab'
import { SubjectsTab } from '@/components/setup/SubjectsTab'
import { TeachersTab } from '@/components/setup/TeachersTab'
import { YearsTab } from '@/components/setup/YearsTab'
import { GlassCard, PageWrapper } from '@/components/ui'
import { cn } from '@/lib/cn'
import type { SetupTab } from '@/types/setup'

interface TabDef {
  id: SetupTab
  label: string
  icon: LucideIcon
}

const TABS: readonly TabDef[] = [
  { id: 'years', label: 'Academic Years', icon: CalendarRange },
  { id: 'classes', label: 'Classes', icon: School },
  { id: 'subjects', label: 'Subjects', icon: BookOpen },
  { id: 'teachers', label: 'Teachers', icon: Users },
  { id: 'students', label: 'Students', icon: GraduationCap },
  { id: 'exams', label: 'Exams', icon: ClipboardList },
]

function isTab(value: string | null): value is SetupTab {
  return TABS.some((t) => t.id === value)
}

function TabPanel({ tab }: { tab: SetupTab }) {
  switch (tab) {
    case 'years':
      return <YearsTab />
    case 'classes':
      return <ClassesTab />
    case 'subjects':
      return <SubjectsTab />
    case 'teachers':
      return <TeachersTab />
    case 'students':
      return <StudentsTab />
    case 'exams':
      return <ExamsTab />
  }
}

export default function SetupPage() {
  const [params, setParams] = useSearchParams()
  const raw = params.get('tab')
  const active: SetupTab = isTab(raw) ? raw : 'years'
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  const select = (tab: SetupTab) => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('tab', tab)
        return next
      },
      { replace: true },
    )
  }

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const idx = TABS.findIndex((t) => t.id === active)
    const delta = e.key === 'ArrowRight' ? 1 : -1
    const next = TABS[(idx + delta + TABS.length) % TABS.length]
    select(next.id)
    tabRefs.current[next.id]?.focus()
  }

  return (
    <PageWrapper title="Academic Setup" description="Years, classes, subjects, teachers, students and exams.">
      <div
        role="tablist"
        aria-label="Setup sections"
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className="mb-6 flex gap-1 overflow-x-auto rounded-2xl border border-slate-200 bg-white/70 p-1 dark:border-slate-800 dark:bg-slate-900/60"
      >
        {TABS.map((t) => {
          const selected = t.id === active
          const Icon = t.icon
          return (
            <button
              key={t.id}
              ref={(el) => {
                tabRefs.current[t.id] = el
              }}
              type="button"
              role="tab"
              id={`setup-tab-${t.id}`}
              aria-selected={selected}
              aria-controls={`setup-panel-${t.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => select(t.id)}
              className={cn(
                'relative flex shrink-0 items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors',
                selected
                  ? 'text-brand-700 dark:text-white'
                  : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200',
              )}
            >
              {selected && (
                <motion.span
                  layoutId="setup-tab-indicator"
                  className="absolute inset-0 rounded-xl bg-brand-50 dark:bg-brand-900/40"
                  transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                />
              )}
              <Icon aria-hidden className="relative size-4" />
              <span className="relative">{t.label}</span>
            </button>
          )
        })}
      </div>
      <GlassCard hoverable={false}>
        <div role="tabpanel" id={`setup-panel-${active}`} aria-labelledby={`setup-tab-${active}`}>
          <TabPanel tab={active} />
        </div>
      </GlassCard>
    </PageWrapper>
  )
}
