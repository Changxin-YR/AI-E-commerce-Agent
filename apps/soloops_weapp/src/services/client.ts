export interface RequestOptions {
  url: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  header: Record<string, string>
  data?: unknown
  timeout: number
}
export type Transport = (
  options: RequestOptions,
) => Promise<{ statusCode: number; data: unknown }>
export interface Session {
  user_id: number
  username: string
  session_id: string
  client_type: string
  expires_at: string
}
interface LoginResult extends Session {
  access_token: string
}
export class ApiError extends Error {
  status: number
  code: string
  constructor(message: string, status = 0, code = 'request_failed') {
    super(message)
    this.status = status
    this.code = code
  }
}
// URL is not guaranteed to exist in the mini-program runtime.
export function normalizeServer(value: string): string {
  const address = value.trim().replace(/\/+$/, '')
  if (
    !/^https:\/\/[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::\d{1,5})?(?:\/[a-z0-9_-]+)*$/i.test(
      address,
    )
  ) {
    throw new ApiError('请输入有效的 HTTPS 服务地址，不含查询参数或账号密码。')
  }
  return address.replace(/\/api$/, '')
}
export class ApiClient {
  private transport: Transport
  private token = ''
  private server = ''
  private generation = 0
  private expiresAt = 0
  onExpired: () => void = () => {}
  constructor(transport: Transport) {
    this.transport = transport
  }
  clear(): void {
    this.token = ''
    this.expiresAt = 0
    this.generation++
  }
  invalidateScope(): void {
    this.generation++
  }
  async login(
    server: string,
    username: string,
    password: string,
  ): Promise<Session> {
    const normalized = normalizeServer(server)
    this.clear()
    this.server = normalized
    const result = await this.request<LoginResult>(
      '/mobile/auth/login',
      'POST',
      {
        username: username.trim(),
        password,
        client_type: 'weapp',
      },
      false,
    )
    const expiry = Date.parse(result.expires_at)
    if (
      !result.access_token ||
      !Number.isFinite(expiry) ||
      expiry <= Date.now()
    )
      throw new ApiError('服务返回了无效会话，请重新登录。')
    this.token = result.access_token
    this.expiresAt = expiry
    const { access_token: _token, ...session } = result
    return session
  }
  async logout(all = false): Promise<void> {
    await this.request<void>(
      all ? '/mobile/auth/logout-all' : '/mobile/auth/logout',
      'POST',
    )
    this.clear()
  }
  async request<T>(
    path: string,
    method: RequestOptions['method'] = 'GET',
    data?: unknown,
    authenticated = true,
    transport: Transport = this.transport,
  ): Promise<T> {
    if (!path.startsWith('/') || path.startsWith('//') || path.includes('..'))
      throw new ApiError('无效的接口路径。')
    if (authenticated && (!this.token || Date.now() >= this.expiresAt)) {
      this.clear()
      this.onExpired()
      throw new ApiError('登录已过期，请重新登录。', 401, 'session_expired')
    }
    const generation = this.generation
    const header: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-SoloOps-Client': 'weapp',
    }
    if (authenticated) header.Authorization = `Bearer ${this.token}`
    let response: { statusCode: number; data: unknown }
    try {
      response = await transport({
        url: `${this.server}/api${path}`,
        method,
        data,
        header,
        timeout: 30000,
      })
    } catch {
      if (generation !== this.generation)
        throw new ApiError('上下文已切换，请刷新。', 0, 'stale_response')
      throw new ApiError(
        '连接失败，请检查网络、服务地址及小程序合法域名配置。',
        0,
        'network_error',
      )
    }
    if (generation !== this.generation)
      throw new ApiError('上下文已切换，请刷新。', 0, 'stale_response')
    if (response.statusCode < 200 || response.statusCode >= 300) {
      if (response.statusCode === 401 && authenticated) {
        this.clear()
        this.onExpired()
      }
      const payload = response.data as {
        error?: { message?: string; code?: string }
      } | null
      throw new ApiError(
        payload?.error?.message || '请求未完成，请重试。',
        response.statusCode,
        payload?.error?.code,
      )
    }
    return (response.statusCode === 204 ? undefined : response.data) as T
  }
}
