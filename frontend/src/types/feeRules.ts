import type { ExpenseContent } from './expenses'
import type { SourceReference } from './analytics'
import type { StatementReconciliation } from './statements'

export const mappingStatuses = {
  mapped: '已按规则分类 · 业务待核',
  unmapped: '未匹配规则 · 待核',
  ambiguous: '重复凭据或规则 · 待核',
  currency_mismatch: '币种不一致 · 待核',
  category_conflict: '与人工费用类别冲突 · 待核',
}
export interface FeeMapping {
  statement_id: number
  status: keyof typeof mappingStatuses
  category: ExpenseContent['category'] | null
  rule_id: number | null
  rule_version: number | null
}
export interface FeeRuleContent {
  fee_name: string
  category: ExpenseContent['category']
  reason: string
}
export interface FeeRuleSaved {
  id: number
  shop_id: number
  data_identity: 'synthetic' | 'user_import'
  channel: StatementReconciliation['scope']['channel']
  status: 'active' | 'withdrawn' | 'cleared'
  version: number
  content: FeeRuleContent | null
  created_at: string
  history: { version: number; action: string; content: FeeRuleContent | null; created_at: string }[]
}
export interface FeeRuleDraft {
  scope: StatementReconciliation['scope']
  rule_id: number | null
  version: number
  content: FeeRuleContent
}
export interface FeeRulePreview {
  preview_hash: string
  source_revision: number
  calculated_at: string
  previous: FeeRuleContent | null
  proposed: FeeRuleContent
  changes: {
    statement_id: number
    fee_name: string
    source: SourceReference
    before: FeeMapping
    after: FeeMapping
  }[]
  statement_count: number
  scope: StatementReconciliation['scope']
}
export interface FeeRuleWrite extends FeeRuleDraft {
  preview_hash: string
  request_id: string
  confirm: true
}
