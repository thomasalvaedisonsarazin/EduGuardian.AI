import { lazy, Suspense } from 'react'
import type { GroupedBarChartProps, PercentLineChartProps } from './Charts'

/* recharts is heavy: load the chart implementations on demand so pages render instantly. */
const PercentLineChartImpl = lazy(() => import('./Charts').then((m) => ({ default: m.PercentLineChart })))
const GroupedBarChartImpl = lazy(() => import('./Charts').then((m) => ({ default: m.GroupedBarChart })))

function ChartFallback() {
  return <div aria-hidden className="h-64 w-full animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800/60" />
}

export function PercentLineChart(props: PercentLineChartProps) {
  return (
    <Suspense fallback={<ChartFallback />}>
      <PercentLineChartImpl {...props} />
    </Suspense>
  )
}

export function GroupedBarChart(props: GroupedBarChartProps) {
  return (
    <Suspense fallback={<ChartFallback />}>
      <GroupedBarChartImpl {...props} />
    </Suspense>
  )
}
