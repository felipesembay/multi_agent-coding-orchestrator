import { describe, expect, it, vi } from 'vitest'
import { request } from './api'
import { mutate } from './projects'
const response = (value: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => value,
})

describe('local API authentication', () => {
  it('bootstraps each protected read and forwards cancellation without storing credentials', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(response({ csrf_token: 'fresh-token' }))
      .mockResolvedValueOnce(response([]))
    vi.stubGlobal('fetch', fetcher)
    const controller = new AbortController()
    await expect(request('/runs', controller.signal)).resolves.toEqual([])
    expect(fetcher).toHaveBeenNthCalledWith(1, '/api/session', {
      signal: controller.signal,
    })
    expect(fetcher).toHaveBeenNthCalledWith(2, '/api/runs', {
      signal: controller.signal,
      headers: { 'X-Orchestrator-CSRF': 'fresh-token' },
    })
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })
  it('keeps health and bootstrap free of token recursion', async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ status: 'ok' }))
    vi.stubGlobal('fetch', fetcher)
    await request('/health')
    await request('/session')
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
  it('uses a fresh token after backend rotation', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(response({ csrf_token: 'before' }))
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response({ csrf_token: 'after' }))
      .mockResolvedValueOnce(response([]))
    vi.stubGlobal('fetch', fetcher)
    await request('/runs')
    await request('/runs')
    expect(fetcher.mock.calls[3][1].headers['X-Orchestrator-CSRF']).toBe(
      'after',
    )
  })
  it('fails closed when bootstrap does not supply a valid token', async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ csrf_token: '' }))
    vi.stubGlobal('fetch', fetcher)
    await expect(request('/settings')).rejects.toThrow('Sessão inválida')
    expect(fetcher).toHaveBeenCalledTimes(1)
    await expect(mutate('/projects', {})).rejects.toThrow('Sessão inválida')
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
  it('does not retry or replay a failed mutation', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(response({ csrf_token: 'token' }))
      .mockResolvedValueOnce(response({ detail: 'Sessão inválida.' }, 403))
    vi.stubGlobal('fetch', fetcher)
    await expect(mutate('/projects', {})).rejects.toThrow('Sessão inválida')
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
