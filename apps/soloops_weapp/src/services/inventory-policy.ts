import type { SourceReference } from './scope-types'
import type { OperationTask } from './operation-types'

export interface InventoryScope {
  data_identity: 'user_import' | 'synthetic'
  channel: string
  max_age_hours: number
  search: string
  offset: number
}
export interface InventoryResult {
  shop_id: number
  source_revision: number
  checked_at: string
  scope: InventoryScope
  items: {
    id: number
    sku: string
    available: number
    safety_threshold: number
    snapshot_at: string
    valid_until: string
    status: 'low' | 'above_threshold' | 'unknown'
    reason: string
    source: SourceReference
  }[]
  has_more: boolean
  note: string
}
export function inventoryScope(query: Record<string, string>): InventoryScope {
  const identity = query.identity || query.data_identity || 'user_import'
  const channel = query.channel || 'generic'
  const hours = Number(query.max_age_hours || 24)
  const search = query.sku || query.search || ''
  if (
    !['user_import', 'synthetic'].includes(identity) ||
    !['generic', 'shopify', 'amazon', 'other'].includes(channel) ||
    !Number.isInteger(hours) ||
    hours < 1 ||
    hours > 720 ||
    search.length > 120
  )
    throw new Error('库存范围无效，请核对身份、渠道、SKU和1–720小时有效时长。')
  return {
    data_identity: identity as InventoryScope['data_identity'],
    channel,
    max_age_hours: hours,
    search,
    offset: 0,
  }
}
export function inventoryTasks(
  tasks: OperationTask[],
  sku: string,
): OperationTask[] {
  return tasks.filter(
    (task) =>
      task.kind === 'low_inventory' && task.snapshot?.object_label === sku,
  )
}
