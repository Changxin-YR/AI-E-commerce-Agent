/**
 * HTTP 客户端：Bearer 鉴权、401 会话失效、错误归一化。
 * 路径一律使用 contracts/ui-contract.json 的 api_ref 路径（含 /api 前缀）。
 */

import Taro from '@tarojs/taro'
import { API_BASE, REQUEST_TIMEOUT_MS } from './config'

export type ApiErrorKind =
  | 'unauthenticated'
  | 'forbidden'
  | 'not_found'
  | 'conflict'
  | 'validation'
  | 'network_unknown'
  | 'server_error'
  | 'unreadable'

const KIND_TEXT: Record<ApiErrorKind, string> = {
  unauthenticated: '登录已过期，请重新登录。',
  forbidden: '没有权限执行此操作，请核对权限与来源后重试。',
  not_found: '对象不存在或不属于当前店铺。',
  conflict: '记录已变化，请回读当前版本后重新审阅。',
  validation: '提交内容未通过校验，请按提示修正字段。',
  network_unknown: '网络中断或超时，写入结果未知；请按记录 ID 回查后再决定。',
  server_error: '服务端处理失败，请稍后重试。',
  unreadable: '服务响应无法读取，请稍后重试。',
}

function kindOf(status: number): ApiErrorKind {
  if (status === 401) return 'unauthenticated'
  if (status === 403) return 'forbidden'
  if (status === 404) return 'not_found'
  if (status === 409) return 'conflict'
  if (status === 422) return 'validation'
  if (status >= 500) return 'server_error'
  return 'validation'
}

/** 归一化后的接口错误；message 可直接展示给用户。 */
export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number
  readonly code: string
  readonly requestId: string

  constructor(
    message: string,
    options: { kind: ApiErrorKind; status?: number; code?: string; requestId?: string },
  ) {
    super(message)
    this.name = 'ApiError'
    this.kind = options.kind
    this.status = options.status ?? 0
    this.code = options.code ?? ''
    this.requestId = options.requestId ?? ''
  }

  /** 写操作结果未知（断线/超时）时必须回读记录核对，不得直接提示成功。 */
  get unknownResult(): boolean {
    return this.kind === 'network_unknown'
  }
}

let authToken: string | null = null
let expiredHandler: (() => void) | null = null
let requestGeneration = 0

export function setAuthToken(token: string | null): void {
  authToken = token
}

export function getAuthToken(): string | null {
  return authToken
}

/** 注册 401 处理；由 store 在启动时挂载。 */
export function onSessionExpired(handler: (() => void) | null): void {
  expiredHandler = handler
}

/** 切换店铺/账号时作废在途请求的结果。 */
export function invalidateRequests(): void {
  requestGeneration += 1
}

export function currentGeneration(): number {
  return requestGeneration
}

export interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** 查询参数；null / undefined / 空串会被丢弃。 */
  query?: Record<string, string | number | boolean | null | undefined>
  /** JSON 请求体。 */
  body?: unknown
  /** 原始二进制请求体（业务文件上传）。 */
  bytes?: ArrayBuffer
  /** 以 ArrayBuffer 读取响应（错误报告 CSV 等下载类接口）。 */
  rawResponse?: boolean
  contentType?: string
}

/** 查询参数拼进 URL，避免与二进制/JSON 请求体争用 data 字段。 */
function buildQuery(query: ApiRequestOptions['query']): string {
  if (!query) return ''
  const parts: string[] = []
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || `${value}` === '') continue
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(`${value}`)}`)
  }
  return parts.length === 0 ? '' : `?${parts.join('&')}`
}

function errorText(payload: unknown, status: number): ApiError {
  const kind = kindOf(status)
  const envelope = payload as { error?: { message?: unknown; code?: unknown; request_id?: unknown } } | null
  const detail = envelope?.error
  const code = detail?.code === undefined ? '' : `${detail.code}`
  const requestId = detail?.request_id === undefined ? '' : `${detail.request_id}`
  const serverMessage = detail?.message === undefined ? '' : `${detail.message}`
  let message = serverMessage || KIND_TEXT[kind]
  if (kind === 'server_error' && requestId) {
    message = `${message}（请求编号 ${requestId}）`
  }
  if (!serverMessage && status && kind === 'validation') {
    message = `请求未完成（${status}）`
  }
  return new ApiError(message, { kind, status, code, requestId })
}

function normalizedCrash(error: unknown, method: string): ApiError {
  const text = error instanceof Error ? error.message : `${error}`
  if (/timeout|超时/i.test(text)) {
    return new ApiError(KIND_TEXT.network_unknown, { kind: 'network_unknown' })
  }
  if (text.includes('domain') || text.includes('合法域名') || text.includes('not in domain list')) {
    return new ApiError(
      '请求域名未加入小程序合法域名；请在后台上传配置或改用校验过的 HTTPS 域名。',
      { kind: 'network_unknown' },
    )
  }
  return new ApiError(
    method === 'GET' ? '暂时无法连接服务，请刷新重试。' : KIND_TEXT.network_unknown,
    { kind: 'network_unknown' },
  )
}

/**
 * 发送请求。path 必须是 api_ref 中的完整路径，例如 '/api/workbench'。
 * 失败统一抛出 ApiError；未知结果不推断成功。
 */
export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  if (!path.startsWith('/') || path.startsWith('//')) {
    throw new ApiError('请求地址无效', { kind: 'unreadable' })
  }
  const method = options.method ?? 'GET'
  const generation = requestGeneration
  const header: Record<string, string> = { 'X-SoloOps-Client': 'mobile' }
  if (authToken) header.Authorization = `Bearer ${authToken}`
  if (options.bytes) {
    header['content-type'] = options.contentType ?? 'application/octet-stream'
  } else if (options.body !== undefined) {
    header['content-type'] = options.contentType ?? 'application/json'
  }

  let response: Taro.request.SuccessCallbackResult<unknown>
  try {
    response = await Taro.request({
      url: `${API_BASE}${path}${buildQuery(options.query)}`,
      method,
      header,
      timeout: REQUEST_TIMEOUT_MS,
      responseType: options.rawResponse ? 'arraybuffer' : 'text',
      dataType: options.rawResponse ? undefined : 'json',
      data: options.bytes ?? (options.body === undefined ? undefined : JSON.stringify(options.body)),
    })
  } catch (error) {
    throw normalizedCrash(error, method)
  }

  if (generation !== requestGeneration) {
    throw new ApiError('当前店铺或账号已变化，请刷新。', { kind: 'conflict' })
  }

  const status = response.statusCode ?? 0
  const raw = response.data
  if (status >= 300) {
    throw errorText(typeof raw === 'string' ? parseJson(raw) : raw, status)
  }
  if (status === 204) return null as T
  if (options.rawResponse) return raw as T
  if (raw === undefined || raw === null || raw === '') return null as T
  if (typeof raw === 'string') {
    const parsed = parseJson(raw)
    if (parsed === undefined) {
      throw new ApiError(KIND_TEXT.unreadable, { kind: 'unreadable', status })
    }
    return parsed as T
  }
  return raw as T
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return undefined
  }
}

/** 带查询参数的 GET，供各页面统一复用。 */
export function apiGet<T>(
  path: string,
  query?: ApiRequestOptions['query'],
): Promise<T> {
  return apiRequest<T>(path, { method: 'GET', query })
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, { method: 'POST', body })
}

/** 生成 request_id（后端幂等键），格式与 Flutter 端一致。 */
export function newRequestId(): string {
  const bytes = new Uint8Array(16)
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Math.floor(Math.random() * 256)
  }
  bytes[6] = (bytes[6] & 15) | 64
  bytes[8] = (bytes[8] & 63) | 128
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

/** 把任意异常转成可展示文本。 */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return `${error}`
}

/** 从响应中安全取出对象/数组，避免页面二次判空。 */
export function asObject<T extends object>(value: unknown): T | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as T) : null
}

export function asRows<T extends object>(value: unknown): T[] {
  return Array.isArray(value) ? (value.filter((row) => row && typeof row === 'object') as T[]) : []
}
