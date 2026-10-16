import { FileSpreadsheet, UploadCloud } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { cn } from '@/lib/cn'

const ACCEPTED_EXTENSIONS = ['.csv', '.xlsx', '.xlsm'] as const

export interface FileDropzoneProps {
  file: File | null
  onFile: (file: File | null) => void
  disabled?: boolean
  maxMb?: number
}

function isAccepted(file: File): boolean {
  const name = file.name.toLowerCase()
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))
}

/** Drag-and-drop (or click to browse) picker for a CSV/XLSX marks file. */
export function FileDropzone({ file, onFile, disabled = false, maxMb = 5 }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const choose = (candidate: File | undefined) => {
    if (!candidate) return
    if (!isAccepted(candidate)) {
      setError('Only .csv and .xlsx files are supported.')
      onFile(null)
      return
    }
    if (candidate.size > maxMb * 1024 * 1024) {
      setError(`The file is larger than ${maxMb} MB.`)
      onFile(null)
      return
    }
    setError(null)
    onFile(candidate)
  }

  const browse = () => {
    if (!disabled) inputRef.current?.click()
  }

  const onDrop = (e: DragEvent<HTMLButtonElement>) => {
    e.preventDefault()
    setDragging(false)
    if (!disabled) choose(e.dataTransfer.files[0])
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        disabled={disabled}
        aria-label={file ? `Selected file ${file.name}. Choose a different file` : 'Choose a marks file to upload'}
        onClick={browse}
        onDragOver={(e) => {
          e.preventDefault()
          if (!disabled) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'flex w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors outline-none',
          'focus-visible:ring-4 focus-visible:ring-brand-500/20',
          dragging
            ? 'border-brand-500 bg-brand-50/70 dark:bg-brand-950/40'
            : 'border-slate-300 bg-white/60 hover:border-brand-400 dark:border-slate-700 dark:bg-slate-900/40',
          disabled && 'cursor-not-allowed opacity-60',
        )}
      >
        {file ? (
          <FileSpreadsheet aria-hidden className="size-10 text-brand-600 dark:text-brand-400" />
        ) : (
          <UploadCloud aria-hidden className="size-10 text-slate-400" />
        )}
        <span className="text-sm font-medium text-slate-800 dark:text-slate-100">
          {file ? file.name : 'Drop a marks file here, or click to browse'}
        </span>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          {file ? `${(file.size / 1024).toFixed(1)} KB` : `CSV or Excel (.xlsx), up to ${maxMb} MB`}
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        aria-label="Marks file"
        accept={ACCEPTED_EXTENSIONS.join(',')}
        className="sr-only"
        tabIndex={-1}
        disabled={disabled}
        onChange={(e) => {
          choose(e.target.files?.[0])
          e.target.value = ''
        }}
      />
      {error && (
        <p role="alert" className="text-sm text-rose-600 dark:text-rose-400">
          {error}
        </p>
      )}
    </div>
  )
}
