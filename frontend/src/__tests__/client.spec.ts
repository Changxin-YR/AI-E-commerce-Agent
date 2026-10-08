import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, request, setCsrfToken } from '@/api/client'

afterEach(() => {
  vi.unstubAllGlobals()
  setCsrfToken('')
})

describe('authenticated requests', () => {
  it('sends session cookies and a CSRF token without a bearer token in storage', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"version":2}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    setCsrfToken('test-csrf')
    await request('/profile', { method: 'PUT', body: '{}' })
    const options = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(options.credentials).toBe('same-origin')
    expect(new Headers(options.headers).get('X-CSRF-Token')).toBe('test-csrf')
  })
  it('preserves a conflict as a failure instead of treating it as a save', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: { code: 'conflict', message: '资料已更新', request_id: 'test-request' },
          }),
          { status: 409 },
        ),
      ),
    )
    await expect(request('/profile', { method: 'PUT', body: '{}' })).rejects.toMatchObject({
      status: 409,
      code: 'conflict',
      requestId: 'test-request',
    })
  })
  it('turns a network failure into actionable feedback', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(request('/profile')).rejects.toBeInstanceOf(ApiError)
  })
})
