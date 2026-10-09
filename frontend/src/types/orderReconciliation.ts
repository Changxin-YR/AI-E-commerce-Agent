import type { SourceReference } from './analytics'
import type { StatementItem, StatementReconciliation } from './statements'

export type OrderReconciliationScope = StatementReconciliation['scope'] & {
  sale_basis: 'unknown' | 'merchandise_after_discount'
  basis_note: string
}
export const orderComparisonStatuses = {
  pending: '待核实',
  amount_difference: '金额差异（所选口径）',
  matched: '金额相同（所选口径）',
}
export const orderComparisonReasons: Record<string, string> = {
  missing_order_reference: '账单缺来源订单号，请补充原文件中的稳定关联编号。',
  order_not_imported: '同范围当前导入记录未找到该订单，不代表业务订单不存在。',
  statement_not_imported: '同范围当前导入记录未找到该类型账单，不代表平台漏记或尚未支付。',
  multiple_order_lines: '订单包含多行；账单未提供可核验的订单行归属，无法分摊。',
  multiple_statement_lines: '同订单包含多笔同类型账单，须核实拆分、重复或调整关系。',
  outside_window: '存在窗口外关联来源；保留依据，请核实跨期关系。',
  currency_mismatch: '两侧币种不一致，缺少已确认的换汇依据。',
  order_status_uncomparable: '存在未付款、取消或测试订单，当前状态不支持销售金额比较。',
  refund_transaction_unknown:
    '行退款为累计值，缺逐笔编号、发生时间、金额组成及支付状态；退款差额未知。',
  refund_amount_unknown: '订单行退款金额未知，请补充原始退款依据。',
  sale_basis_unknown: '销售款金额组成未知，请先核实两侧原文件口径。',
  discount_unknown: '订单行折扣未知，无法计算折后商品款。',
  different_local_date: '账单与订单的当地日期不同，时间归属待核。',
}
export interface ReconciliationOrder {
  id: number
  order_id: string
  line_id: string
  sku: string
  quantity: number
  unit_price: string
  currency: string
  ordered_at: string
  status: string
  discount: string | null
  refund: string | null
  fulfillment_status: string
  in_window: boolean
  source: SourceReference
}
export interface OrderComparison {
  order_id: string
  entry_type: 'sale' | 'refund'
  statement_ids: number[]
  order_line_ids: number[]
  status: keyof typeof orderComparisonStatuses
  reasons: string[]
  currency: string | null
  order_amount: string | null
  difference: string | null
}
export interface OrderReconciliation {
  scope: OrderReconciliationScope
  source_revision: number
  calculated_at: string
  coverage: 'unknown'
  orders: ReconciliationOrder[]
  statements: (StatementItem & { in_window: boolean })[]
  comparisons: OrderComparison[]
  checks: string[]
}
