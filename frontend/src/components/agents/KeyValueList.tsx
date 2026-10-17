import { cn } from '@/lib/cn'
import type { JsonObject, JsonValue } from '@/types'
import { humanizeKey } from './agentMeta'

export interface KeyValueListProps {
  data: JsonObject
  className?: string
  depth?: number
}

function isObject(value: JsonValue): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function Value({ value, depth }: { value: JsonValue; depth: number }) {
  if (value === null) return <span className="text-slate-400">—</span>
  if (typeof value === 'boolean') return <span>{value ? 'Yes' : 'No'}</span>
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-slate-400">None</span>
    if (value.every((v) => !isObject(v) && !Array.isArray(v))) {
      return <span className="break-words">{value.map((v) => (v === null ? '—' : String(v))).join(', ')}</span>
    }
    return (
      <ul className="space-y-2">
        {value.map((item, i) => (
          <li key={i} className="rounded-lg bg-slate-50 p-2 dark:bg-slate-800/60">
            {isObject(item) ? <KeyValueList data={item} depth={depth + 1} /> : <Value value={item} depth={depth + 1} />}
          </li>
        ))}
      </ul>
    )
  }
  if (isObject(value)) {
    if (Object.keys(value).length === 0) return <span className="text-slate-400">None</span>
    return <KeyValueList data={value} depth={depth + 1} />
  }
  return <span className="break-words">{String(value)}</span>
}

/** Readable key/value rendering of arbitrary JSON summaries (staff never see raw JSON). */
export function KeyValueList({ data, className, depth = 0 }: KeyValueListProps) {
  const entries = Object.entries(data)
  if (entries.length === 0) return <p className="text-sm text-slate-400">No details.</p>
  return (
    <dl
      className={cn(
        'grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[minmax(8rem,auto)_1fr]',
        depth > 0 && 'text-xs',
        className,
      )}
    >
      {entries.map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="font-medium text-slate-500 dark:text-slate-400">{humanizeKey(key)}</dt>
          <dd className="min-w-0 text-slate-800 dark:text-slate-200">
            <Value value={value} depth={depth} />
          </dd>
        </div>
      ))}
    </dl>
  )
}
