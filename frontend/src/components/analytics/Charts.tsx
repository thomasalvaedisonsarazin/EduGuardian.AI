import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { cn } from '@/lib/cn'
import { seriesColor, useChartTheme, type ChartTheme } from './chartTheme'

/** One row per x-axis category; series values keyed by series key (null = no data). */
export type ChartDatum = { label: string } & Record<string, string | number | null>

export interface ChartSeries {
  key: string
  name: string
}

const HEIGHTS = { sm: 'h-56', md: 'h-64', lg: 'h-72' } as const
type ChartHeight = keyof typeof HEIGHTS

function tooltipStyle(theme: ChartTheme) {
  return {
    contentStyle: {
      background: theme.tooltipBg,
      border: `1px solid ${theme.tooltipBorder}`,
      borderRadius: 12,
      color: theme.tooltipText,
      fontSize: 12,
    },
    labelStyle: { color: theme.tooltipText, fontWeight: 600 },
    itemStyle: { color: theme.tooltipText },
  }
}

function pctFormatter(value: unknown): string {
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? `${n.toFixed(1)}%` : '—'
}

function pctTick(value: number): string {
  return `${value}%`
}

export interface PercentLineChartProps {
  data: readonly ChartDatum[]
  series: readonly ChartSeries[]
  height?: ChartHeight
  ariaLabel: string
}

/** Percentages over exams on a single 0-100 axis. */
export function PercentLineChart({ data, series, height = 'md', ariaLabel }: PercentLineChartProps) {
  const theme = useChartTheme()
  return (
    <figure aria-label={ariaLabel} className={cn('m-0 w-full', HEIGHTS[height])}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={[...data]} margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
          <CartesianGrid stroke={theme.grid} vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: theme.axis, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: theme.grid }}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: theme.axis, fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={pctTick}
          />
          <Tooltip
            formatter={pctFormatter}
            cursor={{ stroke: theme.axis, strokeDasharray: '3 3' }}
            {...tooltipStyle(theme)}
          />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: theme.axis }} />}
          {series.map((s, i) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={seriesColor(theme, i)}
              strokeWidth={2}
              dot={{ r: 4, strokeWidth: 2, fill: theme.tooltipBg }}
              activeDot={{ r: 6 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </figure>
  )
}

export interface GroupedBarChartProps {
  data: readonly ChartDatum[]
  series: readonly ChartSeries[]
  height?: ChartHeight
  ariaLabel: string
  /** Percentage axis (0-100) when true; plain counts otherwise. */
  percent?: boolean
}

/** One bar per series side by side within each category (e.g. sections within a subject). */
export function GroupedBarChart({ data, series, height = 'lg', ariaLabel, percent = true }: GroupedBarChartProps) {
  const theme = useChartTheme()
  return (
    <figure aria-label={ariaLabel} className={cn('m-0 w-full', HEIGHTS[height])}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={[...data]} margin={{ top: 8, right: 16, bottom: 4, left: -8 }} barGap={2} barCategoryGap="20%">
          <CartesianGrid stroke={theme.grid} vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: theme.axis, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: theme.grid }}
          />
          {percent ? (
            <YAxis
              domain={[0, 100]}
              tick={{ fill: theme.axis, fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={pctTick}
            />
          ) : (
            <YAxis allowDecimals={false} tick={{ fill: theme.axis, fontSize: 12 }} tickLine={false} axisLine={false} />
          )}
          {percent ? (
            <Tooltip formatter={pctFormatter} cursor={{ fill: theme.cursor }} {...tooltipStyle(theme)} />
          ) : (
            <Tooltip cursor={{ fill: theme.cursor }} {...tooltipStyle(theme)} />
          )}
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: theme.axis }} />}
          {series.map((s, i) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.name}
              fill={seriesColor(theme, i)}
              radius={[4, 4, 0, 0]}
              maxBarSize={48}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}
