/**
 * 会话：登录 / 登出 / 持久化。
 * 与 Flutter 端一致，使用移动端 Bearer 会话入口 /api/mobile/auth/*，
 * 令牌与当前服务地址写入 Taro 本地存储。
 */

import Taro from '@tarojs/taro'
import { ApiError, apiGet, apiPost, setAuthToken } from './api'
import { API_BASE, CLIENT_TYPE, SESSION_STORAGE_KEY } from './config'

export interface StoredSession {
  baseUrl: string
  token: string
}

export interface MobileSession {
  user_id: number
  username: string
  session_id: string
  client_type: string
  expires_at: string
}

export interface MobileLoginResult extends MobileSession {
  access_token: string
  token_type: string
}

export interface ShopRecord {
  id: number
  name: string
  market?: string
  currency?: string
  timezone?: string
  platform?: string
}

/** 读取本地会话；不存在或结构不合法时返回 null。 */
export async function readStoredSession(): Promise<StoredSession | null> {
  try {
    const result = await Taro.getStorage({ key: SESSION_STORAGE_KEY })
    const raw = result.data
    if (!raw || typeof raw !== 'object') return null
    const record = raw as Partial<StoredSession>
    if (typeof record.token !== 'string' || record.token === '') return null
    return { baseUrl: `${record.baseUrl ?? ''}`, token: record.token }
  } catch {
    return null
  }
}

export async function writeStoredSession(session: StoredSession): Promise<void> {
  await Taro.setStorage({ key: SESSION_STORAGE_KEY, data: session })
}

export async function clearStoredSession(): Promise<void> {
  try {
    await Taro.removeStorage({ key: SESSION_STORAGE_KEY })
  } catch {
    // 本地存储清理失败不应阻塞登出流程。
  }
}

/**
 * 移动端登录。client_type=weapp 由后端 MobileLoginInput 允许。
 * 返回结果中不含 access_token，令牌已交由 api 层持有。
 */
export async function loginRequest(
  username: string,
  password: string,
): Promise<MobileSession> {
  const result = await apiPost<MobileLoginResult>('/api/mobile/auth/login', {
    username: username.trim(),
    password,
    client_type: CLIENT_TYPE,
  })
  if (!result || typeof result.access_token !== 'string' || result.access_token === '') {
    throw new ApiError('服务未返回有效登录凭据，请重试登录。', { kind: 'unreadable' })
  }
  setAuthToken(result.access_token)
  const { access_token: _token, token_type: _type, ...session } = result
  try {
    await writeStoredSession({ baseUrl: API_BASE, token: result.access_token })
  } catch {
    // 凭据未落盘时立即回滚，避免出现“看似已登录但下次启动失效”的状态。
    try {
      await apiPost('/api/mobile/auth/logout')
    } catch {
      // 回滚登出失败不改变结论：本次登录不成立。
    }
    setAuthToken(null)
    throw new ApiError('设备凭据未能保存，请重试登录。', { kind: 'unreadable' })
  }
  return session
}

/** 校验并回读当前会话（后端注册为 GET /api/mobile/auth/session）。 */
export function readSession(): Promise<MobileSession> {
  return apiGet<MobileSession>('/api/mobile/auth/session')
}

export async function logoutRequest(all = false): Promise<void> {
  await apiPost(all ? '/api/mobile/auth/logout-all' : '/api/mobile/auth/logout')
}

export function loadShops(): Promise<ShopRecord[]> {
  return apiGet<ShopRecord[]>('/api/shops')
}
