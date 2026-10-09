import type { ExpenseSummary } from './expenses'
import type { StatementItem } from './statements'
type ExpenseScope = ExpenseSummary['scope']

export const settlementStatuses = {
  active: '登记依据未变',
  stale: '来源已变化 · 待重核',
  withdrawn: '已撤销',
  cleared: '已清除',
}
export const payoutStatuses = {
  matched: '凭据金额一致 · 银行待核',
  amount_difference: '金额差异',
  statement_only: '未登记到账凭据',
  receipt_only: '缺少平台回款',
  ambiguous: '重复或拆分凭据 · 待核',
  currency_mismatch: '币种不同 · 待核',
  missing_reference: '平台缺少回款凭据号',
}
export interface ManualReceipt {
  payout_ref: string
  receipt_ref: string
  amount: string
  currency: string
  received_at: string
  timezone: string
  note: string
}
export interface SettlementContent {
  statement_id: string
  note: string
  receipts: ManualReceipt[]
}
export interface SettlementDraft {
  scope: ExpenseScope
  settlement_id: number | null
  version: number
  content: SettlementContent
}
export interface SettlementSnapshot {
  scope: ExpenseScope
  content: SettlementContent
  source_revision: number
  calculated_at: string
  statements: StatementItem[]
  totals: { currency: string; entry_type: string; amount: string; count: number }[]
  comparisons: {
    payout_ref: string
    status: keyof typeof payoutStatuses
    statement_ids: number[]
    receipt_indexes: number[]
    difference: string | null
  }[]
  outside_cycle_ids: number[]
  coverage_status: 'unknown'
  balance_status: 'unknown'
  bank_status: 'unverified'
  checks: string[]
}
export interface SettlementPreview {
  preview_hash: string
  snapshot: SettlementSnapshot
}
export interface SettlementWrite extends SettlementDraft {
  preview_hash: string
  request_id: string
  confirm: true
}
export interface SettlementSaved {
  id: number
  shop_id: number
  data_identity: ExpenseScope['data_identity']
  channel: ExpenseScope['channel']
  status: keyof typeof settlementStatuses
  version: number
  content_version: number
  created_at: string
  snapshot: SettlementSnapshot | null
  history: { version: number; action: string; has_content: boolean; created_at: string }[]
}
export interface SettlementCurrent {
  record: SettlementSaved
  preview: SettlementPreview | null
}
