import type { SourceReference } from './analytics'
import type { SourceChannel } from './imports'

export interface InventoryScope {
  data_identity: 'user_import' | 'synthetic'
  channel: SourceChannel
  max_age_hours: number
  search: string
  offset: number
}
export interface InventoryItem {
  id: number
  sku: string
  channel: string
  available: number
  safety_threshold: number
  snapshot_at: string
  valid_until: string
  status: 'low' | 'above_threshold' | 'unknown'
  reason: string
  source: SourceReference
}
export interface InventoryResult {
  shop_id: number
  source_revision: number
  checked_at: string
  scope: InventoryScope
  items: InventoryItem[]
  has_more: boolean
  note: string
}
