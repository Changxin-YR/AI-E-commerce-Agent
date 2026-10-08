import type { SourceReference } from './analytics'

export interface ListingContent {
  title: string
  description: string
}
export interface ProductFacts {
  product_id: number
  sku: string
  name: string
  facts: string
  source: SourceReference
}
export interface ListingVersion {
  id: number
  shop_id: number
  number: number
  version: number
  status: 'draft' | 'approved' | 'rejected' | 'superseded'
  source_status: 'current' | 'stale' | 'cleared'
  base_version_id: number | null
  engine: string
  snapshot: {
    product: ProductFacts
    before: ListingContent
    proposed: ListingContent
    missing: string[]
    blockers: string[]
  } | null
  created_at: string
  decided_at: string | null
  external_status: 'not_submitted'
  risk: 'R1'
}
export interface ProductWorkspace {
  product: ProductFacts
  active_id: number | null
  active_version: ListingVersion | null
  versions: ListingVersion[]
}
export const listingStatus: Record<ListingVersion['status'], string> = {
  draft: '等待审批',
  approved: '本地已批准',
  rejected: '已拒绝',
  superseded: '已被后续版本替代',
}
export const sourceStatus: Record<ListingVersion['source_status'], string> = {
  current: '来源有效',
  stale: '来源已变化，需重新生成',
  cleared: '来源已清除',
}
