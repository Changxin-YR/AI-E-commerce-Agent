/**
 * 轻量全局状态（Vue reactive）。
 * 只保存会话、店铺与全局提示；业务数据由各页面自行读取，避免跨页缓存失真。
 */

import { reactive } from 'vue'
import Taro from '@tarojs/taro'
import {
  ApiError,
  currentGeneration,
  errorMessage,
  invalidateRequests,
  onSessionExpired,
  setAuthToken,
} from './api'
import { API_BASE, normalizeBaseUrl } from './config'
import {
  clearStoredSession,
  loadShops,
  loginRequest,
  logoutRequest,
  readSession,
  readStoredSession,
  type MobileSession,
  type ShopRecord,
} from './session'

export interface AppStore {
  baseUrl: string
  session: MobileSession | null
  shops: ShopRecord[]
  shopId: number | null
  /** 启动引导是否完成；未完成前页面不应发起业务请求。 */
  bootstrapped: boolean
  loading: boolean
  notice: string
  /** 会话是否已失效（401 或登出）。 */
  expired: boolean
}

export const state = reactive<AppStore>({
  baseUrl: API_BASE,
  session: null,
  shops: [],
  shopId: null,
  bootstrapped: false,
  loading: false,
  notice: '',
  expired: false,
})

/** 当前店铺记录；未选择时返回 null。 */
export function currentShop(): ShopRecord | null {
  return state.shops.find((shop) => shop.id === state.shopId) ?? null
}

/**
 * 业务时区取服务端返回的店铺时区；缺失时交由页面显示“未知”，
 * 不在这里回落到手机时区。
 */
export function shopTimezone(): string {
  const zone = currentShop()?.timezone
  return typeof zone === 'string' && zone.trim() !== '' ? zone.trim() : 'UTC'
}

export function shopCurrency(): string {
  const currency = currentShop()?.currency
  return typeof currency === 'string' && currency.trim() !== '' ? currency.trim().toUpperCase() : ''
}

/**
 * 拼接店铺资源路径。路径必须来自 contracts/ui-contract.json 的 api_ref，
 * 例如 shopPath('/inventory') → /api/shops/3/inventory。
 */
export function shopPath(suffix: string): string {
  if (state.shopId === null) {
    throw new ApiError('请先创建或选择一家店铺。', { kind: 'validation' })
  }
  return `/api/shops/${state.shopId}${suffix}`
}

/** 是否已登录（本地判定，随后由 readSession 回读确认）。 */
export function isLoggedIn(): boolean {
  return state.session !== null
}

function resetSession(notice: string): void {
  invalidateRequests()
  setAuthToken(null)
  state.session = null
  state.shops = []
  state.shopId = null
  state.expired = true
  state.notice = notice
}

onSessionExpired(() => {
  resetSession('登录已过期，请重新登录。')
  void clearStoredSession()
})

/** 启动引导：恢复本地会话 → 回读会话 → 载入店铺。失败只提示，不伪造登录态。 */
export async function bootstrap(): Promise<void> {
  if (state.bootstrapped) return
  state.loading = true
  try {
    const stored = await readStoredSession()
    if (!stored || normalizeBaseUrl(stored.baseUrl) !== API_BASE) {
      state.session = null
      return
    }
    setAuthToken(stored.token)
    state.session = await readSession()
    await loadShopList()
    state.notice = ''
  } catch (error) {
    if (error instanceof ApiError && error.kind === 'unauthenticated') {
      resetSession('登录已过期，请重新登录。')
      await clearStoredSession()
    } else {
      state.notice = errorMessage(error)
    }
  } finally {
    state.loading = false
    state.bootstrapped = true
  }
}

export async function loadShopList(): Promise<void> {
  const generation = currentGeneration()
  const shops = await loadShops()
  if (generation !== currentGeneration()) return
  state.shops = Array.isArray(shops) ? shops : []
  if (!state.shops.some((shop) => shop.id === state.shopId)) {
    state.shopId = state.shops.length > 0 ? state.shops[0].id : null
  }
}

export async function login(username: string, password: string): Promise<void> {
  const session = await loginRequest(username, password)
  state.session = session
  state.expired = false
  state.notice = ''
  await loadShopList()
}

export async function logout(all = false): Promise<void> {
  try {
    await logoutRequest(all)
  } catch {
    // 服务端登出失败也要清空本地会话，避免留下可用令牌。
  }
  await clearStoredSession()
  resetSession('')
  state.expired = false
}

/** 切换店铺：作废在途请求结果，避免旧店铺数据写进新上下文。 */
export function selectShop(shopId: number): void {
  if (state.shopId === shopId) return
  invalidateRequests()
  state.shopId = shopId
}

/** 回读会话与店铺；用于从后台返回或长时间离开后调用。 */
export async function refreshSession(): Promise<void> {
  if (state.session === null) return
  try {
    state.session = await readSession()
    await loadShopList()
  } catch (error) {
    if (!(error instanceof ApiError && error.kind === 'unauthenticated')) {
      state.notice = errorMessage(error)
    }
  }
}

/** 页面级统一动作包装：返回错误文本，成功返回空串。 */
export async function perform(action: () => Promise<void>): Promise<string> {
  state.loading = true
  try {
    await action()
    return ''
  } catch (error) {
    if (error instanceof ApiError && error.kind === 'unauthenticated') {
      state.notice = error.message
    }
    return errorMessage(error)
  } finally {
    state.loading = false
  }
}

/** 业务页会话门禁：未登录时回到登录页并返回 false，不发起业务请求。 */
export async function ensureSession(): Promise<boolean> {
  if (!state.bootstrapped) await bootstrap()
  if (state.session === null) {
    await Taro.reLaunch({ url: '/pages/login/index' })
    return false
  }
  return true
}
