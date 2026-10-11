export interface AnalysisScope {
  cost_mode?: 'current_estimate' | 'seller_history'
  start_at: string
  end_at: string
  timezone: string
  currency: string
  data_identity: 'synthetic' | 'user_import'
  channel?: string | null
  intent: 'summary' | 'sales' | 'low_margin'
  min_quantity: number
  max_margin_percent: string
}
export interface SourceReference {
  origin?: string
  batch_id: number
  row_id: number
  row_number: number
  filename: string
  sheet_name: string
  exported_at: string | null
  imported_at: string
  data_identity: string
}
