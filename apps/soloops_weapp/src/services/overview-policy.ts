import type { SourceReference } from './scope-types'

export interface OverviewScope {
  shop_ids: number[]
  start_date: string
  end_date: string
  comparison_start: string | null
  comparison_end: string | null
  timezone: string
  data_identity: 'user_import' | 'synthetic'
  currencies: string[]
  max_age_hours: number
  min_quantity: number
  max_margin_percent: string
}
export interface OverviewResult {
  scope: OverviewScope
  engine: string
  calculated_at: string
  valid_until: string | null
  shops: {
    shop_id: number
    shop_name: string
    platform: string
    market: string
    source_revision: number
    currencies: {
      currency: string
      current: {
        analysis: {
          summary: { sales: string | null; gross_profit: string | null }
        }
        top_skus: string[]
        orders: number | null
        refunds: string | null
        pending_orders: number | null
        unknown_fulfillment_lines: number
        pending_sources: SourceReference[]
      }
    }[]
    inventory_low: number | null
    inventory_unknown: number
    message_count: number | null
    tasks: { id: number; kind: string; status: string; source_status: string }[]
    tasks_has_more: boolean
    sources: SourceReference[]
  }[]
  totals: {
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
  }[]
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
export function checkedOverviewScope(value: OverviewScope): OverviewScope {
  const start = Date.parse(`${value.start_date}T00:00:00Z`),
    end = Date.parse(`${value.end_date}T00:00:00Z`)
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(value.start_date) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(value.end_date) ||
    end <= start ||
    end - start > 366 * 86400000
  )
    throw new Error('日期窗口须为1–366天，结束日期不计入。')
  if (
    !value.shop_ids.length ||
    value.shop_ids.length > 20 ||
    new Set(value.shop_ids).size !== value.shop_ids.length
  )
    throw new Error('请选择1–20家不重复店铺。')
  if (
    !['user_import', 'synthetic'].includes(value.data_identity) ||
    value.max_age_hours < 1 ||
    value.max_age_hours > 720 ||
    !Number.isInteger(value.min_quantity) ||
    value.min_quantity < 1
  )
    throw new Error('总览范围参数无效。')
  if (new Set(value.currencies).size !== value.currencies.length)
    throw new Error('币种范围无效。')
  try {
    new Intl.DateTimeFormat('en', { timeZone: value.timezone })
  } catch {
    throw new Error('统计时区无效。')
  }
  return {
    ...value,
    shop_ids: [...value.shop_ids].sort(),
    currencies: [...new Set(value.currencies)],
  }
}
