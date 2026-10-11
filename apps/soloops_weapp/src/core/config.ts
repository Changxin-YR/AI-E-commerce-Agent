/**
 * 运行期配置：后端地址、超时、客户端标识。
 * 默认本机开发端口；构建时可用 TARO_APP_API_BASE 覆盖。
 */

const DEFAULT_API_BASE = 'http://127.0.0.1:18080'

/** 去掉末尾斜杠，空值回落到默认地址。 */
export function normalizeBaseUrl(raw: string | undefined | null): string {
  const value = `${raw ?? ''}`.trim().replace(/\/+$/, '')
  return value === '' ? DEFAULT_API_BASE : value
}

/**
 * 读取构建期注入的 TARO_APP_API_BASE。
 * 小程序运行时没有 process 全局对象，未注入时必须安全回落到默认地址。
 */
function envApiBase(): string {
  try {
    return process.env.TARO_APP_API_BASE ?? ''
  } catch {
    return ''
  }
}

/** 后端服务根地址（不含 /api 前缀）。 */
export const API_BASE: string = normalizeBaseUrl(envApiBase())

/** 请求超时；写操作超时后按“结果未知”处理，由页面回读记录核对。 */
export const REQUEST_TIMEOUT_MS = 45000

/** 单次响应最大读取字节数，避免一次性拉爆小程序内存。 */
export const MAX_RESPONSE_BYTES = 8 * 1024 * 1024

/** 与后端 ImportParser.MAX_BYTES 一致：单个业务文件 2 MiB。 */
export const MAX_UPLOAD_BYTES = 2 * 1024 * 1024

/** 移动端登录使用的客户端类型，后端 MobileLoginInput 允许 ohos / android / weapp。 */
export const CLIENT_TYPE = 'weapp'

/** 会话存储键；与 Flutter 端保存内容语义一致（服务地址 + 令牌）。 */
export const SESSION_STORAGE_KEY = 'soloops_session'

/** 默认业务时区，仅用于展示兜底；页面应优先使用服务端返回的 timezone。 */
export const DEFAULT_TIMEZONE = 'Asia/Shanghai'
