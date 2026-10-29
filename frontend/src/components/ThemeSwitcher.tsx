import { useEffect, useState } from 'react'
import './ThemeSwitcher.css'

export type ThemeOption = 'system' | 'light' | 'dark'

const THEME_STORAGE_KEY = 'tax_reconcile_theme'

export function ThemeSwitcher() {
  const [theme, setTheme] = useState<ThemeOption>(() => {
    return (localStorage.getItem(THEME_STORAGE_KEY) as ThemeOption) || 'system'
  })

  useEffect(() => {
    const root = document.documentElement
    root.setAttribute('data-theme', theme)
    localStorage.setItem(THEME_STORAGE_KEY, theme)
  }, [theme])

  const handleKeyDown = (e: React.KeyboardEvent, option: ThemeOption) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault()
      setTheme(option)
    }
  }

  return (
    <fieldset id="color-scheme" className="theme-switcher" aria-label="Theme switcher">
      <legend>Theme</legend>

      <label
        htmlFor="theme-system"
        tabIndex={0}
        onKeyDown={(e) => handleKeyDown(e, 'system')}
      >
        <input
          type="radio"
          id="theme-system"
          name="theme"
          value="system"
          tabIndex={-1}
          checked={theme === 'system'}
          onChange={() => setTheme('system')}
        />
        <span>Sys</span>
      </label>

      <label
        htmlFor="theme-light"
        tabIndex={0}
        onKeyDown={(e) => handleKeyDown(e, 'light')}
      >
        <input
          type="radio"
          id="theme-light"
          name="theme"
          value="light"
          tabIndex={-1}
          checked={theme === 'light'}
          onChange={() => setTheme('light')}
        />
        <span>Light</span>
      </label>

      <label
        htmlFor="theme-dark"
        tabIndex={0}
        onKeyDown={(e) => handleKeyDown(e, 'dark')}
      >
        <input
          type="radio"
          id="theme-dark"
          name="theme"
          value="dark"
          tabIndex={-1}
          checked={theme === 'dark'}
          onChange={() => setTheme('dark')}
        />
        <span>Dark</span>
      </label>
    </fieldset>
  )
}
