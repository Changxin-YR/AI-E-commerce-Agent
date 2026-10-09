import type { SourceReference } from './analytics'
import type { SourceChannel } from './imports'

export interface QualityScope {
  data_identity: 'user_import' | 'synthetic'
  channel: SourceChannel | null
  sku_prefix: string
}
export interface QualityIssue {
  code: string
  field: string
  status: 'missing' | 'review'
  reason: string
  suggestion: string
}
export interface QualityProduct {
  product_id: number
  sku: string
  name: string
  facts: string
  price: string | null
  currency: string | null
  unit_cost: string | null
  cost_currency: string | null
  channel: string
  source: SourceReference
  issues: QualityIssue[]
  similar_skus: string[]
  similar_sku_count: number
}
export interface QualityResult {
  shop_id: number
  scope: QualityScope
  source_revision: number
  checked_at: string
  rule_version: string
  preview_hash: string
  product_count: number
  affected_products: number
  missing_count: number
  review_count: number
  coverage: { code: string; label: string; status: 'checked' | 'not_checked'; reason: string }[]
  limitations: string[]
  products: QualityProduct[]
}
export interface QualitySaved {
  id: number
  shop_id: number
  status: 'current' | 'stale' | 'cleared'
  created_at: string
  scope: QualityScope
  snapshot: QualityResult | null
}
export interface QualityPage {
  items: QualitySaved[]
  next_cursor: number | null
}
export const qualityStatus = {
  current: '来源未变化',
  stale: '来源已变化，需重新检查',
  cleared: '正文已清除',
}
export const qualityChannels = {
  generic: '通用 / 自建表',
  shopify: 'Shopify',
  amazon: 'Amazon',
  other: '其他来源',
}
