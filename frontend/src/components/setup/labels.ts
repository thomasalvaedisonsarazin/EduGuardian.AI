/** Display helpers for setup entities (kept out of .tsx files for fast-refresh). */
import type { AcademicYear, ClassSection, ID } from '@/types'

export function classLabel(c: Pick<ClassSection, 'grade' | 'section'>): string {
  return `${c.grade}-${c.section}`
}

export function nameById<T extends { id: ID }>(items: readonly T[] | undefined, label: (item: T) => string) {
  const map = new Map<ID, string>()
  for (const item of items ?? []) map.set(item.id, label(item))
  return (id: ID | null | undefined): string => (id == null ? '—' : (map.get(id) ?? `#${id}`))
}

export function currentYearId(years: readonly AcademicYear[] | undefined): ID | undefined {
  return years?.find((y) => y.is_current)?.id ?? years?.[0]?.id
}

export function toNumberOrNull(value: string): number | null {
  if (value.trim() === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}
