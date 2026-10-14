import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, request, requestStream, setCsrfToken } from '@/api/client'

afterEach(() => {
  vi.unstubAllGlobals()
  setCsrfToken('')
})

function streamResponse(chunks: Uint8Array[]): Response {
  return new Response(
    new ReadableStream({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(chunk))
        controller.close()
      },
    }),
    { headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } },
  )
}

describe('execution streams', () => {
  it('preserves UTF-8 and SSE frames split across chunks, sends CSRF, and returns only the final result', async () => {
    const encoded = new TextEncoder().encode(
      ': heartbeat\r\n\r\nevent: status\r\ndata: {"message":"执行中"}\r\n\r\n' +
        'event: delta\r\ndata: {"text":"库存"}\r\n\r\n' +
        'event: result\r\ndata: {"id":3,"status":"waiting_approval"}\r\n\r\n',
    )
    const fetchMock = vi
      .fn()
      .mockResolvedValue(streamResponse(Array.from(encoded, (byte) => new Uint8Array([byte]))))
    vi.stubGlobal('fetch', fetchMock)
    setCsrfToken('stream-csrf')
    const onEvent = vi.fn()
    const result = await requestStream(
      '/shops/1/agent/runs/3/stream',
      { method: 'POST', body: '{"action":"advance"}' },
      onEvent,
    )
    expect(result).toEqual({ id: 3, status: 'waiting_approval' })
    expect(onEvent.mock.calls.map(([event]) => event)).toEqual([
      { event: 'status', data: { message: '执行中' } },
      { event: 'delta', data: { text: '库存' } },
    ])
    const options = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(options.credentials).toBe('same-origin')
    expect(new Headers(options.headers).get('X-CSRF-Token')).toBe('stream-csrf')
    expect(new Headers(options.headers).get('Accept')).toBe('text/event-stream')
  })

  it.each([
    ['event: delta\ndata: {"text":"partial"}\n\n', 'stream_interrupted'],
    ['event: delta\ndata: broken\n\n', 'invalid_stream'],
    ['event: error\ndata: {"code":"source_changed","message":"来源已变化"}\n\n', 'source_changed'],
  ])('does not claim completion or retry when the stream fails (%s)', async (body, code) => {
    const fetchMock = vi.fn().mockResolvedValue(streamResponse([new TextEncoder().encode(body)]))
    vi.stubGlobal('fetch', fetchMock)
    await expect(requestStream('/agent/stream', { method: 'POST' }, vi.fn())).rejects.toMatchObject(
      { code },
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('handles expired sessions before consuming a stream', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })))
    const listener = vi.fn()
    window.addEventListener('soloops:session-expired', listener)
    try {
      await expect(
        requestStream('/agent/stream', { method: 'POST' }, vi.fn()),
      ).rejects.toMatchObject({ status: 401 })
      expect(listener).toHaveBeenCalledOnce()
    } finally {
      window.removeEventListener('soloops:session-expired', listener)
    }
  })
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
