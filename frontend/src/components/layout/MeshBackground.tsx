/** Soft animated gradient backdrop for landing/auth pages. */
export function MeshBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-brand-50 via-white to-accent-50 dark:from-slate-950 dark:via-slate-950 dark:to-brand-950" />
      <div className="absolute -top-24 left-1/4 size-[28rem] animate-pulse rounded-full bg-brand-200 opacity-40 blur-3xl dark:bg-brand-800/40" />
      <div className="absolute right-1/5 -bottom-24 size-[28rem] animate-pulse rounded-full bg-accent-200 opacity-40 blur-3xl [animation-delay:1.5s] dark:bg-accent-800/30" />
    </div>
  )
}
