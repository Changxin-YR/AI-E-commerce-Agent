import { request } from './client'
import type {
  ExpenseOrder,
  ExpenseSaved,
  ExpenseScope,
  ExpenseSummary,
  ExpenseWrite,
} from '@/types/expenses'

const root = (shop: number) => `/shops/${shop}/expenses`
export const expensesApi = {
  get: (shop: number, id: number) => request<ExpenseSaved>(`${root(shop)}/${id}`),
  list: (shop: number, scope: ExpenseScope, before?: number) =>
    request<{ items: ExpenseSaved[]; next_cursor: number | null }>(
      `${root(shop)}?${new URLSearchParams({ ...scope, ...(before ? { before: String(before) } : {}) })}`,
    ),
  write: (shop: number, data: ExpenseWrite, id?: number) =>
    request<ExpenseSaved>(`${root(shop)}${id ? `/${id}` : ''}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  control: (
    shop: number,
    id: number,
    action: 'withdraw' | 'clear',
    data: { version: number; request_id: string; confirm: true },
  ) =>
    request<ExpenseSaved>(`${root(shop)}/${id}/${action}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  orders: (shop: number, scope: ExpenseScope, order: string) =>
    request<{ source_revision: number; items: ExpenseOrder[] }>(
      `${root(shop)}/orders?${new URLSearchParams({ ...scope, order_id: order })}`,
    ),
  summary: (shop: number, data: ExpenseSummary['scope']) =>
    request<ExpenseSummary>(`${root(shop)}/summary`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}
