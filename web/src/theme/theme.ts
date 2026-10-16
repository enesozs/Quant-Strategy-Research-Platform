import { createContext, useContext } from 'react'

export type Theme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'strategy-lab-theme'

export const ThemeContext = createContext<{ theme: Theme; toggle: () => void }>({
  theme: 'dark',
  toggle: () => {},
})

export function useTheme() {
  return useContext(ThemeContext)
}
