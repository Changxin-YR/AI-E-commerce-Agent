import { request } from './client'
import type { InventoryResult, InventoryScope } from '@/types/inventory'

export const inventoryApi = {
  list: (shop: number, scope: InventoryScope) => {
    const query = new URLSearchParams(
      Object.entries(scope).map(([key, value]) => [key, String(value)]),
    )
    return request<InventoryResult>(`/shops/${shop}/inventory?${query}`)
  },
}
