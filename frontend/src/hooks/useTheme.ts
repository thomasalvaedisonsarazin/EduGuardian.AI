import { useContext } from 'react'
import { ThemeContext, type ThemeContextValue } from '@/context/theme-context'

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>')
  return ctx
}
