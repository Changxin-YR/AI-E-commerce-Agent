/**
 * 业务链接映射：把工作台返回的 Web 路径（contracts/ui-contract.json 的 web_route）
 * 映射到小程序页面。未实现的路由明确提示，不猜测跳转目标。
 */

import Taro from '@tarojs/taro'
import { state } from './store'

export interface TabEntry {
  key: string
  title: string
  page: string
}

/** 5 大入口，与契约 entries 一致：首页 / 待办 / AI / 客服 / 我的。 */
export const tabEntries: TabEntry[] = [
  { key: 'home', title: '首页', page: '/pages/home/index' },
  { key: 'tasks', title: '待办', page: '/pages/tasks/index' },
  { key: 'ai', title: 'AI', page: '/pages/agent/index' },
  { key: 'support', title: '客服', page: '/pages/support/index' },
  { key: 'mine', title: '我的', page: '/pages/mine/index' },
]

/** Web 路由 → 小程序页面。仅登记第一波已实现的页面。 */
const BUSINESS_ROUTES: Record<string, string> = {
  '/': '/pages/tasks/index',
  '/imports': '/pages/imports/index',
  '/inventory': '/pages/inventory/index',
  '/listings': '/pages/listings/index',
  '/support': '/pages/support/index',
  '/agent': '/pages/agent/index',
  '/login': '/pages/login/index',
}

/** 制表符页无法接收参数，用挂起意图在目标页 onShow 时取用。 */
const pendingIntents = new Map<string, Record<string, string>>()

export function setPendingIntent(page: string, query: Record<string, string>): void {
  pendingIntents.set(page, { ...query })
}

export function takePendingIntent(page: string): Record<string, string> | null {
  const found = pendingIntents.get(page)
  if (!found) return null
  pendingIntents.delete(page)
  return found
}

function isTabPage(page: string): boolean {
  return tabEntries.some((entry) => entry.page === page)
}

function toast(title: string): void {
  void Taro.showToast({ title, icon: 'none' })
}

/**
 * 打开工作台事项链接。
 * 店铺不一致时按 Flutter 端同样口径提示先切换店铺，不跨店打开记录。
 */
export async function openWorkPath(
  path: string,
  query: Record<string, string> = {},
): Promise<void> {
  const target = BUSINESS_ROUTES[path]
  if (!target) {
    toast('无法识别此业务链接，请从业务工具打开。')
    return
  }
  const shop = Number(query.shop ?? '')
  if (Number.isFinite(shop) && shop > 0 && shop !== state.shopId) {
    toast('请先切换到此记录所属店铺，再打开记录。')
    return
  }
  if (isTabPage(target)) {
    setPendingIntent(target, query)
    await Taro.switchTab({ url: target })
    return
  }
  const suffix = Object.entries(query)
    .filter(([, value]) => `${value}` !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&')
  await Taro.navigateTo({ url: suffix === '' ? target : `${target}?${suffix}` })
}

/** 切换制表符页。 */
export function openTab(page: string): void {
  void Taro.switchTab({ url: page })
}

/** 当前页面的查询参数（仅 navigateTo 打开的非制表符页可用）。 */
export function pageQuery(): Record<string, string> {
  const params = Taro.getCurrentInstance().router?.params
  if (!params) return {}
  const result: Record<string, string> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && `${value}` !== '') result[key] = `${value}`
  }
  return result
}

/** 打开非制表符页面，可选查询参数。 */
export function openPage(page: string, query: Record<string, string> = {}): void {
  const suffix = Object.entries(query)
    .filter(([, value]) => `${value}` !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&')
  void Taro.navigateTo({ url: suffix === '' ? page : `${page}?${suffix}` })
}
