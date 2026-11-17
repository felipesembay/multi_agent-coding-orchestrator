import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ThemeToggle } from '../components/ThemeToggle'

describe('theme preference', () => {
  it('starts dark, switches to light and restores the saved preference', async () => {
    const view = render(<ThemeToggle />)
    expect(document.documentElement.dataset.theme).toBe('dark')
    await userEvent.click(
      screen.getByRole('button', { name: 'Ativar tema claro' }),
    )
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('orch-theme')).toBe('light')
    view.unmount()
    render(<ThemeToggle />)
    expect(
      screen.getByRole('button', { name: 'Ativar tema escuro' }),
    ).toBeInTheDocument()
    await userEvent.click(
      screen.getByRole('button', { name: 'Ativar tema escuro' }),
    )
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
  it('remains usable when storage cannot be written', async () => {
    const setter = vi
      .spyOn(Storage.prototype, 'setItem')
      .mockImplementation(() => {
        throw new Error('Storage unavailable')
      })
    try {
      render(<ThemeToggle />)
      await userEvent.click(
        screen.getByRole('button', { name: 'Ativar tema claro' }),
      )
      expect(document.documentElement.dataset.theme).toBe('light')
    } finally {
      setter.mockRestore()
    }
  })
})
