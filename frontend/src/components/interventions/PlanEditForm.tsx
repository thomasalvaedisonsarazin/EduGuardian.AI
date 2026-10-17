import { Plus, Save, Trash2, X } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { GradientButton } from '@/components/ui'
import type { ActivityOwner, InterventionItem, InterventionUpdateInput, PlanActivity } from '@/types/interventions'

export interface PlanEditFormProps {
  item: InterventionItem
  saving?: boolean
  onSave: (input: InterventionUpdateInput) => void
  onCancel: () => void
}

const OWNERS: readonly ActivityOwner[] = ['teacher', 'student', 'parent']

const fieldClass =
  'w-full rounded-lg border border-slate-200 bg-white/80 px-3 py-2 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-100'

const emptyActivity: PlanActivity = { title: '', description: '', frequency: 'Weekly', owner: 'teacher' }

/** Inline editor for a draft plan's text, activities and reassessment date. */
export function PlanEditForm({ item, saving = false, onSave, onCancel }: PlanEditFormProps) {
  const id = useId()
  const [planText, setPlanText] = useState(item.plan_text)
  const [activities, setActivities] = useState<PlanActivity[]>(item.activities.map((a) => ({ ...a })))
  const [reassessOn, setReassessOn] = useState(item.reassess_on ?? '')
  const [error, setError] = useState<string | null>(null)

  const patch = (index: number, changes: Partial<PlanActivity>) =>
    setActivities((prev) => prev.map((a, i) => (i === index ? { ...a, ...changes } : a)))

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!planText.trim()) {
      setError('The plan text cannot be empty.')
      return
    }
    if (activities.some((a) => !a.title.trim() || !a.description.trim() || !a.frequency.trim())) {
      setError('Every activity needs a title, a description and a frequency.')
      return
    }
    setError(null)
    onSave({ plan_text: planText.trim(), activities, reassess_on: reassessOn || null })
  }

  return (
    <form onSubmit={submit} aria-label="Edit plan" className="space-y-4">
      <div className="space-y-1">
        <label htmlFor={`${id}-text`} className="text-sm font-medium text-slate-700 dark:text-slate-200">
          Plan text
        </label>
        <textarea
          id={`${id}-text`}
          rows={8}
          value={planText}
          onChange={(e) => setPlanText(e.target.value)}
          className={fieldClass}
        />
      </div>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium text-slate-700 dark:text-slate-200">Activities</legend>
        {activities.map((a, i) => (
          <div key={i} className="grid gap-2 rounded-xl border border-slate-200 p-3 sm:grid-cols-2 dark:border-slate-700">
            <input
              aria-label={`Activity ${i + 1} title`}
              value={a.title}
              onChange={(e) => patch(i, { title: e.target.value })}
              placeholder="Title"
              className={fieldClass}
            />
            <div className="flex gap-2">
              <input
                aria-label={`Activity ${i + 1} frequency`}
                value={a.frequency}
                onChange={(e) => patch(i, { frequency: e.target.value })}
                placeholder="Frequency"
                className={fieldClass}
              />
              <select
                aria-label={`Activity ${i + 1} owner`}
                value={a.owner}
                onChange={(e) => patch(i, { owner: e.target.value as ActivityOwner })}
                className={fieldClass}
              >
                {OWNERS.map((o) => (
                  <option key={o} value={o}>
                    {o.charAt(0).toUpperCase() + o.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <textarea
              aria-label={`Activity ${i + 1} description`}
              rows={2}
              value={a.description}
              onChange={(e) => patch(i, { description: e.target.value })}
              placeholder="Description"
              className={`${fieldClass} sm:col-span-2`}
            />
            <div className="sm:col-span-2">
              <GradientButton
                variant="ghost"
                size="sm"
                icon={Trash2}
                onClick={() => setActivities((prev) => prev.filter((_, j) => j !== i))}
              >
                Remove activity
              </GradientButton>
            </div>
          </div>
        ))}
        <GradientButton
          variant="secondary"
          size="sm"
          icon={Plus}
          disabled={activities.length >= 12}
          onClick={() => setActivities((prev) => [...prev, { ...emptyActivity }])}
        >
          Add activity
        </GradientButton>
      </fieldset>

      <div className="space-y-1">
        <label htmlFor={`${id}-date`} className="text-sm font-medium text-slate-700 dark:text-slate-200">
          Reassess on
        </label>
        <input
          id={`${id}-date`}
          type="date"
          value={reassessOn}
          onChange={(e) => setReassessOn(e.target.value)}
          className={`${fieldClass} max-w-xs`}
        />
      </div>

      {error && (
        <p role="alert" className="text-sm text-rose-600 dark:text-rose-400">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <GradientButton type="submit" icon={Save} loading={saving}>
          Save changes
        </GradientButton>
        <GradientButton variant="ghost" icon={X} onClick={onCancel} disabled={saving}>
          Cancel
        </GradientButton>
      </div>
    </form>
  )
}
