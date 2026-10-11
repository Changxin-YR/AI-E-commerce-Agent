import { Capacitor } from '@capacitor/core'
import { apiEndpoint } from '@/lib/apiEndpoint'

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

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const native = Capacitor.isNativePlatform()
  let url: string
  try {
    url = apiEndpoint(path, native, import.meta.env.VITE_SOLOOPS_API_ORIGIN)
  } catch (error) {
    throw new ApiError(errorMessage(error), 0, 'api_configuration_error', '')
  }
  const headers = new Headers(options.headers)
  headers.set('X-SoloOps-Client', 'web')
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (csrfToken) headers.set('X-CSRF-Token', csrfToken)
  let response: Response
  try {
    // CapacitorHttp patches fetch on Android, including binary file uploads.
    // Keep the server's existing client marker, HttpOnly session and CSRF contract.
    response = await fetch(url, {
      ...options,
      headers,
      credentials: native ? 'include' : 'same-origin',
    })
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
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '操作未完成，请重试。'
}
