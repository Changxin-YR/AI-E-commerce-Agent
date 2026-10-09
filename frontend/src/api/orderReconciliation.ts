import { request } from './client'
import type { OrderReconciliation, OrderReconciliationScope } from '@/types/orderReconciliation'

export const orderReconciliationApi = {
  reconcile: (shop: number, scope: OrderReconciliationScope) =>
    request<OrderReconciliation>(`/shops/${shop}/statements/orders/reconcile`, {
      method: 'POST',
      body: JSON.stringify(scope),
    }),
}
