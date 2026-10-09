import type { SourceReference } from './analytics'
import type { SourceChannel } from './imports'

export interface ProductValues {
  sku: string
  name: string
  facts: string
  price: string | null
  currency: string | null
  unit_cost: string | null
  cost_currency: string | null
}
export interface ProductChange {
  product_id: number
  expected_source_row_id: number
  name: string
  facts: string
}
export interface EditCreate {
  data_identity: 'synthetic' | 'user_import'
  channel: SourceChannel
  reason: string
  changes: ProductChange[]
  request_id: string
}
export interface EditItem {
  product_id: number
  before: ProductValues
  after: ProductValues
  source: SourceReference
  result: 'pending' | 'applied' | 'conflict' | 'blocked'
  message: string
}
export interface EditSaved {
  id: number
  shop_id: number
  version: number
  status: 'draft' | 'applied' | 'failed' | 'rejected' | 'stale' | 'revoked' | 'cleared'
  preview_hash: string
  snapshot: {
    source_revision: number
    data_identity: 'synthetic' | 'user_import'
    channel: SourceChannel
    reason: string
    items: EditItem[]
  } | null
  output_batch_id: number | null
  created_at: string
  decided_at: string | null
  current_count: number
}
export type EditAction = 'approve' | 'reject' | 'withdraw' | 'clear'
export const editStatuses = {
  draft: '待审批草稿',
  applied: '本地已生效',
  failed: '整批未生效',
  rejected: '已拒绝',
  stale: '来源已失效',
  revoked: '已撤销',
  cleared: '正文已清除',
}
