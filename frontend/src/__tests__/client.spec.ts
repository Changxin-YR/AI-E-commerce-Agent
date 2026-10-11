import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, request, setCsrfToken } from '@/api/client'
import { Capacitor } from '@capacitor/core'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
  setCsrfToken('')
})

describe('authenticated requests', () => {
  it('sends native requests to the configured API with CSRF and existing client identity', async () => {
    vi.spyOn(Capacitor, 'isNativePlatform').mockReturnValue(true)
    vi.stubEnv('VITE_SOLOOPS_API_ORIGIN', 'https://ops.example.com')
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    setCsrfToken('native-csrf')
    await request('/profile', { method: 'PUT', body: '{}' })
    expect(fetchMock.mock.calls[0]?.[0]).toBe('https://ops.example.com/api/profile')
    const options = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(options.credentials).toBe('include')
    expect(new Headers(options.headers).get('X-CSRF-Token')).toBe('native-csrf')
    expect(new Headers(options.headers).get('X-SoloOps-Client')).toBe('web')
  })
  it('does not send credentials when a native endpoint is missing', async () => {
    vi.spyOn(Capacitor, 'isNativePlatform').mockReturnValue(true)
    vi.stubEnv('VITE_SOLOOPS_API_ORIGIN', '')
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    await expect(request('/auth/login', { method: 'POST', body: '{}' })).rejects.toMatchObject({
      code: 'api_configuration_error',
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })
  it('passes uploaded file bytes to the fetch bridge unchanged', async () => {
    vi.spyOn(Capacitor, 'isNativePlatform').mockReturnValue(true)
    vi.stubEnv('VITE_SOLOOPS_API_ORIGIN', 'https://ops.example.com')
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const file = new File(['sku,quantity\na,1'], 'inventory.csv')
    await request('/shops/1/imports', {
      method: 'POST',
      body: file,
      headers: { 'Content-Type': 'application/octet-stream' },
    })
    const options = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(options.body).toBe(file)
    expect(new Headers(options.headers).get('Content-Type')).toBe('application/octet-stream')
  })
  it('expires the UI session on an authenticated 401', async () => {
    const listener = vi.fn()
    window.addEventListener('soloops:session-expired', listener)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })))
    try {
      await expect(request('/profile')).rejects.toMatchObject({ status: 401 })
      expect(listener).toHaveBeenCalledOnce()
    } finally {
      window.removeEventListener('soloops:session-expired', listener)
    }
  })
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
