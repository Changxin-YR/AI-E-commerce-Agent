interface ErrorPayload {
  error?: { code?: string; message?: string; request_id?: string }
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly requestId: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

let csrfToken = ''
export function setCsrfToken(value: string): void {
  csrfToken = value
}

async function fetchResponse(path: string, options: RequestInit): Promise<Response> {
  const headers = new Headers(options.headers)
  headers.set('X-SoloOps-Client', 'web')
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (csrfToken) headers.set('X-CSRF-Token', csrfToken)
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...options, headers, credentials: 'same-origin' })
  } catch {
    throw new ApiError('暂时无法连接服务，请检查服务状态后重试。', 0, 'network_error', '')
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ErrorPayload
    if (response.status === 401 && !path.startsWith('/auth/')) {
      window.dispatchEvent(new Event('soloops:session-expired'))
    }
    throw new ApiError(
      payload.error?.message ?? '请求未完成，请稍后重试。',
      response.status,
      payload.error?.code ?? 'request_failed',
      payload.error?.request_id ?? '',
    )
  }
  return response
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetchResponse(path, options)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export interface StreamEvent {
  event: string
  data: unknown
}

/** A POST stream never retries: a disconnected request may already have executed. */
export async function requestStream<T>(
  path: string,
  options: RequestInit,
  onEvent: (event: StreamEvent) => void,
): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'text/event-stream')
  const response = await fetchResponse(path, { ...options, headers })
  if (!response.body || !response.headers.get('Content-Type')?.includes('text/event-stream')) {
    throw new ApiError('服务未返回执行流，请刷新执行记录核对任务。', 0, 'invalid_stream', '')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      if (buffer.length > 512_000)
        throw new ApiError('执行流内容超过限制，请刷新执行记录。', 0, 'invalid_stream', '')
      // Keep incomplete UTF-8 characters and SSE frames for the next network chunk.
      let boundary: RegExpExecArray | null
      while ((boundary = /\r?\n\r?\n/.exec(buffer))) {
        const frame = buffer.slice(0, boundary.index)
        buffer = buffer.slice(boundary.index + boundary[0].length)
        let event = 'message'
        const data: string[] = []
        for (const line of frame.split(/\r?\n/)) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''))
        }
        if (!data.length) continue
        let payload: unknown
        try {
          payload = JSON.parse(data.join('\n'))
        } catch {
          throw new ApiError('执行流格式异常，请刷新执行记录核对任务。', 0, 'invalid_stream', '')
        }
        if (event === 'error') {
          const error = payload as { code?: string; message?: string } | null
          throw new ApiError(
            typeof error?.message === 'string' ? error.message : '任务执行未完成，请刷新执行记录。',
            0,
            typeof error?.code === 'string' ? error.code : 'stream_error',
            '',
          )
        }
        if (event === 'result') return payload as T
        onEvent({ event, data: payload })
      }
      if (done) break
    }
    throw new ApiError(
      '连接已中断，请刷新执行记录核对结果；任务不会自动重发。',
      0,
      'stream_interrupted',
      '',
    )
  } catch (cause) {
    if (cause instanceof ApiError) throw cause
    throw new ApiError(
      '连接已中断，请刷新执行记录核对结果；任务不会自动重发。',
      0,
      'stream_interrupted',
      '',
    )
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '操作未完成，请重试。'
}
