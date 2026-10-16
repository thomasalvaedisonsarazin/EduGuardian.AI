import { motion, type Variants } from 'framer-motion'
import type { Key, ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface AnimatedListProps<T> {
  items: readonly T[]
  getKey: (item: T, index: number) => Key
  renderItem: (item: T, index: number) => ReactNode
  className?: string
  itemClassName?: string
  /** Seconds between each item entrance (default 0.06). */
  stagger?: number
  /** Rendered when `items` is empty. */
  empty?: ReactNode
}

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.25, ease: 'easeOut' } },
}

/** Staggered list. Renders a <ul>; each item is wrapped in an animated <li>. */
export function AnimatedList<T>({
  items,
  getKey,
  renderItem,
  className,
  itemClassName,
  stagger = 0.06,
  empty,
}: AnimatedListProps<T>) {
  if (items.length === 0 && empty) return <>{empty}</>
  return (
    <motion.ul
      initial="hidden"
      animate="visible"
      variants={{ hidden: {}, visible: { transition: { staggerChildren: stagger } } }}
      className={cn('space-y-3', className)}
    >
      {items.map((item, i) => (
        <motion.li key={getKey(item, i)} variants={itemVariants} className={itemClassName}>
          {renderItem(item, i)}
        </motion.li>
      ))}
    </motion.ul>
  )
}
