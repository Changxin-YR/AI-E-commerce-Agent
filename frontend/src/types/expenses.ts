import type { SourceReference } from './analytics'
import type { SourceChannel } from './imports'
type DataIdentity = 'user_import' | 'synthetic'

export const expenseCategories = {
  shipping: '物流',
  packaging: '包装',
  storage: '仓储',
  platform: '平台服务',
  advertising: '广告',
  tax: '税费',
  other: '其他自定义费用',
}
export const expenseStatuses = {
  active: '已录入 · 账单待核对',
  stale: '来源变化 · 待重核',
  withdrawn: '已撤销',
  cleared: '正文已清除',
}
export interface ExpenseContent {
  label: string
  category: keyof typeof expenseCategories
  amount: string
  currency: string
  occurred_at: string
  timezone: string
  evidence_ref: string
  evidence_note: string
  allocation: 'shop' | 'order_line'
  order_line_id: number | null
  expected_source_row_id: number | null
  expected_source_revision: number | null
  reason: string
}
export interface ExpenseSnapshot {
  content: ExpenseContent
  source: SourceReference | null
  order_id: string | null
  line_id: string | null
  sku: string | null
  order_status: string | null
}
export interface ExpenseSaved {
  id: number
  shop_id: number
  data_identity: DataIdentity
  channel: SourceChannel
  version: number
  status: keyof typeof expenseStatuses
  created_at: string
  snapshot: ExpenseSnapshot | null
  history: {
    version: number
    action: string
    created_at: string
    snapshot: ExpenseSnapshot | null
  }[]
}
export interface ExpenseScope {
  data_identity: DataIdentity
  channel: SourceChannel
}
export interface ExpenseWrite extends ExpenseScope {
  request_id: string
  confirm: true
  version: number
  content: ExpenseContent
}
export interface ExpenseOrder {
  id: number
  order_id: string
  line_id: string
  sku: string
  currency: string
  status: string
  source: SourceReference
}
export interface ExpenseSummary {
  scope: ExpenseScope & { start_at: string; end_at: string; timezone: string }
  totals: {
    currency: string
    category: keyof typeof expenseCategories
    allocation: string
    amount: string
    count: number
  }[]
  included_count: number
  stale_count: number
  withdrawn_count: number
  checks: string[]
}
