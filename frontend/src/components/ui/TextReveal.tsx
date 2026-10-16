import { motion } from 'framer-motion'
import { cn } from '@/lib/cn'

export interface TextRevealProps {
  text: string
  as?: 'h1' | 'h2' | 'h3' | 'p'
  className?: string
}

/** Word-by-word reveal for hero/auth headlines. */
export function TextReveal({ text, as = 'h1', className }: TextRevealProps) {
  const Tag = motion[as]
  const words = text.split(' ')
  return (
    <Tag
      aria-label={text}
      initial="hidden"
      animate="visible"
      variants={{ visible: { transition: { staggerChildren: 0.05 } } }}
      className={cn('flex flex-wrap gap-x-[0.25em]', className)}
    >
      {words.map((word, i) => (
        <motion.span key={`${word}-${i}`} aria-hidden variants={{ hidden: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0 } }}>
          {word}
        </motion.span>
      ))}
    </Tag>
  )
}
