import { request } from './client'
import type { OperationScope } from '@/types/operations'

export interface RuleValues {
  max_age_hours: number
  min_quantity: number
  max_margin_percent: string
  advertising_daily_budget: string | null
  currency: string
  notes: {
    target_site: string
    warehouse: string
    logistics: string
    brand_voice: string
    support_wording: string
  }
  basis: string
  automation: 'manual_only'
}
export interface BusinessRule {
  version: number
  previous_version: number
  restored_from: number | null
  shop_id: number
  channel: string
  data_identity: string
  action: string
  active: boolean
  values: RuleValues
  created_at: string | null
}
export type RuleAction = 'save' | 'revoke' | 'reset' | 'restore'
export const rulesApi = {
  current: (shop: number, channel: string, identity: string) =>
    request<BusinessRule>(
      `/shops/${shop}/business-rules?channel=${channel}&data_identity=${identity}`,
    ),
  history: (shop: number, channel: string, identity: string, before?: number) =>
    request<BusinessRule[]>(
      `/shops/${shop}/business-rules/history?channel=${channel}&data_identity=${identity}${before ? `&before=${before}` : ''}`,
    ),
  get: (shop: number, version: number) =>
    request<BusinessRule>(`/shops/${shop}/business-rules/${version}`),
  change: (rule: BusinessRule, action: RuleAction, values?: RuleValues, restore_version?: number) =>
    request<BusinessRule>(`/shops/${rule.shop_id}/business-rules`, {
      method: 'POST',
      body: JSON.stringify({
        channel: rule.channel,
        data_identity: rule.data_identity,
        expected_version: rule.version,
        action,
        values,
        restore_version,
      }),
    }),
}
export function applyRule(scope: OperationScope, rule: BusinessRule): void {
  scope.rule_revision_id = rule.version
  scope.max_age_hours = rule.values.max_age_hours
  scope.min_quantity = rule.values.min_quantity
  scope.max_margin_percent = rule.values.max_margin_percent
}
