import type { AnalysisResult, SourceReference } from './analytics'
import type { InventoryItem } from './inventory'

export interface OverviewScope {
  shop_ids: number[]
  start_date: string
  end_date: string
  comparison_start: string | null
  comparison_end: string | null
  timezone: string
  data_identity: 'synthetic' | 'user_import'
  currencies: string[]
  max_age_hours: number
  min_quantity: number
  max_margin_percent: string
}
export interface PeriodMetrics {
  analysis: AnalysisResult
  orders: number | null
  refunds: string | null
  known_refunds: string
  refund_known_lines: number
  pending_orders: number | null
  unknown_fulfillment_lines: number
  pending_sources: SourceReference[]
  top_skus: string[]
}
export interface CurrencyGroup {
  currency: string
  current: PeriodMetrics
  comparison: PeriodMetrics
  sales_change: string | null
  sales_change_percent: string | null
}
export interface ShopOverview {
  shop_id: number
  shop_name: string
  platform: string
  market: string
  source_revision: number
  currencies: CurrencyGroup[]
  inventory: InventoryItem[]
  inventory_low: number | null
  inventory_unknown: number
  messages: { message_id: string; channel: string; sent_at: string; source: SourceReference }[]
  message_count: number | null
  tasks: { id: number; kind: string; status: string; source_status: string }[]
  tasks_has_more: boolean
  sources: SourceReference[]
}
export interface CurrencyTotal {
  currency: string
  shop_ids: number[]
  sales: string | null
  known_sales: string
  comparison_sales: string | null
  sales_change: string | null
  sales_change_percent: string | null
  gross_profit: string | null
  known_gross_profit: string
  refunds: string | null
  known_refunds: string
  observed_orders: number
  warnings: string[]
}
export interface OverviewResult {
  scope: OverviewScope
  engine: 'local_rules'
  calculated_at: string
  valid_until: string | null
  shops: ShopOverview[]
  totals: CurrencyTotal[]
  summary: string[]
  limitations: string[]
}
export interface OverviewSaved {
  id: number
  status: string
  created_at: string
  scope: OverviewScope
  snapshot: OverviewResult | null
}
export interface OverviewPage {
  items: OverviewSaved[]
  next_cursor: number | null
}
