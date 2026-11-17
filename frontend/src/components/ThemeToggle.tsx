import { useEffect, useLayoutEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import { Button } from './ui/button'

type Theme = 'dark' | 'light'
function savedTheme(): Theme {
  try {
    return localStorage.getItem('orch-theme') === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(savedTheme)
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('orch-theme', theme)
    } catch {
      /* Still usable when storage is unavailable. */
    }
  }, [theme])
  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === 'orch-theme' || event.key === null)
        setTheme(savedTheme())
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])
  const label = theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro'
  return (
    <Button
      className="theme-toggle"
      size="icon"
      aria-label={label}
      title={label}
      onClick={() =>
        setTheme((previous) => (previous === 'dark' ? 'light' : 'dark'))
      }
    >
      {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
    </Button>
  )
}
