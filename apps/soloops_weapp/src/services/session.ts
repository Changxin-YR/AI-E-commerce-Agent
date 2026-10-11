import { reactive } from 'vue'
import Taro from '@tarojs/taro'
import { ApiClient, type Session } from './client'
export interface Shop {
  id: number
  code: string
  name: string
  platform: string
  market: string
  currency: string
  timezone: string
  connection_status: string
}
export const account = reactive({
  session: null as Session | null,
  shops: [] as Shop[],
  shopId: 0,
  notice: '',
})
export const api = new ApiClient((options) =>
  Taro.request({ ...options, data: options.data as object | undefined }),
)
export function clearAccount(): void {
  api.clear()
  account.session = null
  account.shops = []
  account.shopId = 0
}
api.onExpired = () => {
  clearAccount()
  account.notice = '登录已过期，请重新登录。'
}
export function selectShop(id: number): void {
  if (!account.shops.some((shop) => shop.id === id)) return
  api.invalidateScope()
  account.shopId = id
}
export async function loadShops(): Promise<void> {
  const shops = await api.request<Shop[]>('/shops')
  account.shops = shops
  if (!shops.some((shop) => shop.id === account.shopId))
    selectShop(shops[0]?.id || 0)
  if (!shops.length) account.shopId = 0
}
