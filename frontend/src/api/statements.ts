import { request } from './client'
import type { StatementReconciliation } from '@/types/statements'

export const statementsApi = {
  reconcile: (shop: number, scope: StatementReconciliation['scope']) =>
    request<StatementReconciliation>(`/shops/${shop}/statements/reconcile`, {
      method: 'POST',
      body: JSON.stringify(scope),
    }),
}
