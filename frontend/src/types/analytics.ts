export interface AnalysisScope {
  start_at: string
  end_at: string
  timezone: string
  currency: string
  data_identity: 'synthetic' | 'user_import'
  intent: 'summary' | 'sales' | 'low_margin'
  min_quantity: number
  max_margin_percent: string
}
export interface SourceReference {
  batch_id: number
  row_id: number
  row_number: number
  filename: string
  sheet_name: string
  exported_at: string | null
  imported_at: string
  data_identity: string
}
export interface MetricSummary {
  sku: string | null
  line_count: number
  purchased_quantity: number
  sales: string | null
  known_sales_subtotal: string
  sales_known_lines: number
  cost: string | null
  known_cost_subtotal: string
  cost_known_lines: number
  gross_profit: string | null
  known_gross_subtotal: string
  gross_known_lines: number
  margin_percent: string | null
}
export interface AnalysisLine {
  order_id: string
  line_id: string
  sku: string
  status: string
  ordered_at: string
  currency: string
  quantity: number
  included: boolean
  unit_price: string
  discount: string | null
  refund: string | null
  sales: string | null
  cost: string | null
  gross_profit: string | null
  gaps: string[]
  source: SourceReference
  cost_source: SourceReference | null
}
export interface AnalysisResult {
  scope: AnalysisScope
  source_revision: number
  calculated_at: string
  engine: 'local_rules'
  formula: string
  cost_basis: string
  fee_gaps: string[]
  warnings: string[]
  summary: MetricSummary
  skus: MetricSummary[]
  lines: AnalysisLine[]
  ranking_available: boolean
  answer: string
  candidates: string[]
}
export interface SavedAnalysis {
  id: number
  shop_id: number
  source_revision: number
  status: string
  created_at: string
  scope: AnalysisScope
  snapshot: AnalysisResult | null
  todo: { id: number; title: string; status: string } | null
}
export interface SourceDetail {
  reference: SourceReference
  batch_status: string
  raw: Record<string, unknown>
  corrections: Record<string, unknown>
  normalized: Record<string, unknown>
}
