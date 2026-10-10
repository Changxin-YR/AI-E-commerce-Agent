import type { SourceReference } from './analytics'
import type { SourceChannel } from './imports'

export interface PolicyData {
  code: string
  title: string
  topic: 'faq' | 'shipping' | 'refund' | 'warranty'
  text: string
  market: string
  channel: SourceChannel
  language: 'en' | 'zh'
  data_identity: 'user_import' | 'synthetic'
  source: string
  source_version: string
  source_confirmed: boolean
  valid_from: string
  valid_until: string | null
}
export interface Policy {
  id: number
  number: number
  status: string
  availability: string
  data: PolicyData | null
  created_at: string
}
export interface MessageFacts {
  id: number
  message_id: string
  body: string
  language: string
  channel: string
  sent_at: string
  order_id: string
  source: SourceReference
}
export interface OrderFact {
  order_id: string
  line_id: string
  sku: string
  status: string
  fulfillment_status: string
  source: SourceReference
}
export interface ReplyDraft {
  id: number
  version: number
  status: string
  source_status: 'current' | 'stale' | 'cleared'
  engine: string
  snapshot: {
    message: MessageFacts
    orders: OrderFact[]
    order_verified: boolean
    policies: Policy[]
    intents: string[]
    reasons: string[]
    handoff_summary: string
    reply: string
    model_facts?: string[]
  } | null
  created_at: string
  updated_at: string
  external_status: 'not_submitted'
  reviewed_version?: number | null
  reviewed_at?: string | null
  reviewed_language?: string | null
}
export interface SupportContext {
  expected_source_row_id: number
  expected_order_row_ids: number[]
  order_verified: boolean
  policy_ids: number[]
}
export interface SupportWorkspace {
  message: MessageFacts
  orders: OrderFact[]
  policies: Policy[]
  drafts: ReplyDraft[]
  market: string
}
export const replyStatus: Record<string, string> = {
  draft: '待审核草稿',
  human_review: '需要人工',
  archived: '已存档',
}
export const policyStatus: Record<string, string> = {
  effective: '当前有效',
  expired: '已过期',
  future: '尚未生效',
  superseded: '历史版本',
  cleared: '已清除',
}
export const intentLabels: Record<string, string> = {
  shipping: '物流查询',
  refund: '退款 / 退货',
  address_change: '地址变更 / 拦截',
  cancel: '取消订单',
  dispute: '争议 / 赔偿',
  warranty: '保修 / 故障',
  faq: '一般使用咨询',
  unknown: '意图待确认',
}
export function supportTime(value: string, timezone: string): string {
  return `${new Intl.DateTimeFormat('zh-CN', { timeZone: timezone, dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))} (${timezone})`
}

export interface ManualActionInput {
  request_id: string
  expected_version: number
  occurred_at: string
  method: string
  evidence_ref: string
  note: string
  confirmed: boolean
}
export interface ManualActionRecord {
  id: number
  draft_id: number
  draft_version: number
  occurred_at: string
  recorded_at: string
  details: { method: string; evidence_ref: string; note: string } | null
  provenance: 'seller_reported'
  external_status: 'not_submitted'
}
