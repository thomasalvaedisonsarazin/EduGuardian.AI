import { useContext } from 'react'
import { ThemeContext } from '@/context/theme-context'

/**
 * Chart colours derived from the brand tokens (indigo brand, teal accent, then amber, pink).
 * Categorical order is fixed - series keep their colour regardless of filters.
 * Validated with the dataviz palette checker for both surfaces (lightness band, CVD separation,
 * contrast); identity is never colour-alone (legends + tables accompany every chart).
 */
export interface ChartTheme {
  series: readonly string[]
  grid: string
  axis: string
  tooltipBg: string
  tooltipBorder: string
  tooltipText: string
  cursor: string
}

const LIGHT: ChartTheme = {
  series: ['#4f46e5', '#0d9488', '#d97706', '#db2777'],
  grid: '#e2e8f0',
  axis: '#64748b',
  tooltipBg: '#ffffff',
  tooltipBorder: '#e2e8f0',
  tooltipText: '#0f172a',
  cursor: 'rgba(99, 102, 241, 0.08)',
}

const DARK: ChartTheme = {
  series: ['#6366f1', '#0d9488', '#d97706', '#db2777'],
  grid: '#1e293b',
  axis: '#94a3b8',
  tooltipBg: '#0f172a',
  tooltipBorder: '#334155',
  tooltipText: '#f1f5f9',
  cursor: 'rgba(148, 163, 184, 0.12)',
}

/** Theme-aware chart colours; falls back to light outside a ThemeProvider (e.g. tests). */
export function useChartTheme(): ChartTheme {
  const ctx = useContext(ThemeContext)
  return ctx?.resolved === 'dark' ? DARK : LIGHT
}

/** Colour for the n-th series (fixed order; extra series reuse the neutral axis colour). */
export function seriesColor(theme: ChartTheme, index: number): string {
  return theme.series[index] ?? theme.axis
}
