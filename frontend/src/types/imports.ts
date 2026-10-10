export type ImportKind = 'products' | 'orders' | 'messages' | 'inventory' | 'statements'
export type SourceChannel = 'generic' | 'shopify' | 'amazon' | 'other'
export interface FieldDefinition {
  key: string
  label: string
  data_type: string
  required: boolean
  help: string
}
export interface ImportCatalog {
  products: FieldDefinition[]
  orders: FieldDefinition[]
  messages: FieldDefinition[]
  inventory: FieldDefinition[]
  statements: FieldDefinition[]
  max_bytes: number
  max_rows: number
}
export interface MappingTemplate {
  id: number
  name: string
  kind: ImportKind
  source_channel: SourceChannel
  mapping: Record<string, string>
}
export interface ImportRow {
  row_number: number
  raw: Record<string, string>
  corrections: Record<string, string>
  normalized: Record<string, string | number | null>
  previous: Record<string, string | number | null> | null
  errors: { field: string; message: string }[]
  warnings: string[]
  action: 'new' | 'update' | 'unchanged' | 'error'
}
export interface BatchSummary {
  group_id?: number | null
  group_part?: number | null
  origin?: 'file_import' | 'manual_edit'
  id: number
  shop_id: number
  kind: ImportKind
  source_channel: SourceChannel
  data_identity: 'user_import' | 'synthetic'
  filename: string
  sheet_name: string
  timezone: string
  exported_at: string | null
  created_at: string
  expires_at: string
  committed_at: string | null
  status: 'draft' | 'preview' | 'committed' | 'revoked' | 'cleared' | 'expired'
  version: number
  total_rows: number
  valid_rows: number
  error_rows: number
  new_rows: number
  updated_rows: number
  unchanged_rows: number
  currencies: string[]
  coverage_start: string | null
  coverage_end: string | null
}
export interface ImportBatch extends BatchSummary {
  headers: string[]
  examples: Record<string, string>
  mapping: Record<string, string>
  suggestions: { field: string; column: string; confidence: 'exact' | 'candidate' }[]
  suggested_kind: ImportKind
  errors: string[]
  rows: ImportRow[]
  required_reviews?: MappingReview[]
  duplicate_rows?: number
}
export interface MappingReview {
  field: string
  column: string
  label: string
  meaning: string
}
export type Corrections = Record<number, Record<string, string>>

export interface ImportManifest {
  format: 'soloops-split-v1'
  source_filename: string
  source_sha256: string
  total_rows: number
  parts: { filename: string; sha256: string; rows: number; bytes: number }[]
}
export interface ImportGroup {
  id: number
  shop_id: number
  version: number
  status: string
  complete: boolean
  options: Record<string, string | number | null>
  manifest: ImportManifest
  batches: BatchSummary[]
  committed_parts: number
  committed_rows: number
  unique_rows: number
  overlap_rows: number
}
