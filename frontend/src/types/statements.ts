import type { SourceReference } from './analytics'
import type { ExpenseSummary, ExpenseContent } from './expenses'

export const entryTypes = {
  sale: '账单销售款',
  refund: '账单退款',
  fee: '账单费用',
  payout: '平台记载回款 · 到账待核',
}
export const comparisonStatuses = {
  matched: '编号与金额一致',
  amount_difference: '金额差异',
  statement_only: '仅账单有记录',
  expense_only: '仅人工费用有记录',
  ambiguous: '重复编号 · 待人工核对',
  currency_mismatch: '币种不一致',
}
export interface StatementItem {
  id: number
  statement_id: string
  line_id: string
  entry_type: keyof typeof entryTypes
  amount: string
  currency: string
  occurred_at: string
  evidence_ref: string
  fee_name: string
  settlement_id: string
  order_id: string
  note: string
  source: SourceReference
}
export interface FeeComparison {
  evidence_ref: string
  status: keyof typeof comparisonStatuses
  statement_ids: number[]
  expenses: {
    id: number
    version: number
    label: string
    category: ExpenseContent['category']
    allocation: string
    evidence_ref: string
    amount: string
    currency: string
    occurred_at: string
  }[]
  difference: string | null
}
export interface StatementReconciliation {
  scope: ExpenseSummary['scope']
  source_revision: number
  calculated_at: string
  statements: StatementItem[]
  totals: { currency: string; entry_type: keyof typeof entryTypes; amount: string; count: number }[]
  comparisons: FeeComparison[]
  stale_expenses: number
  withdrawn_expenses: number
  checks: string[]
}
