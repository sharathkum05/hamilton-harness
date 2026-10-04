// Light, dark or follow the device. The choice is kept per browser.

import { useCallback, useEffect, useState } from 'react'

export type Theme = 'system' | 'light' | 'dark'

const KEY = 'repkit:theme'

function stored(): Theme {
  try {
    const value = localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(stored)
  const [dark, setDark] = useState(false)

  useEffect(() => {
    const system = window.matchMedia('(prefers-color-scheme: dark)')
    const sync = () => {
      const isDark = theme === 'dark' || (theme === 'system' && system.matches)
      document.documentElement.classList.toggle('dark', isDark)
      setDark(isDark)
    }
    sync()
    system.addEventListener('change', sync)
    return () => system.removeEventListener('change', sync)
  }, [theme])

  const setTheme = useCallback((next: Theme) => {
    try {
      if (next === 'system') localStorage.removeItem(KEY)
      else localStorage.setItem(KEY, next)
    } catch {
      /* the choice still applies for this visit */
    }
    setThemeState(next)
  }, [])

  return { theme, dark, setTheme }
}
