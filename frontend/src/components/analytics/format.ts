/** Formatting helpers for analytics values (backend decimals arrive as strings). */
import type { DecimalString } from '@/types/analytics'

export function toNum(value: DecimalString | number | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : null
}

/** "72.5%" (one decimal), or an em dash when unknown. */
export function fmtPct(value: DecimalString | number | null | undefined, digits = 1): string {
  const n = toNum(value)
  return n === null ? '—' : `${n.toFixed(digits)}%`
}

/** Signed percentage points, e.g. "+8.0 pts" / "−20.0 pts". */
export function fmtDelta(value: DecimalString | number | null | undefined, digits = 1): string {
  const n = toNum(value)
  if (n === null) return '—'
  if (n === 0) return `0.${'0'.repeat(digits)} pts`
  const sign = n > 0 ? '+' : '−'
  return `${sign}${Math.abs(n).toFixed(digits)} pts`
}

/** Plain decimal without trailing ".00" noise, e.g. "34.5", "90". */
export function fmtMarks(value: DecimalString | number | null | undefined): string {
  const n = toNum(value)
  return n === null ? '—' : String(Number(n.toFixed(2)))
}
