import { request } from './client'
import type { FeeRuleDraft, FeeRulePreview, FeeRuleSaved, FeeRuleWrite } from '@/types/feeRules'

export const feeRulesApi = {
  list: (shop: number, scope: FeeRuleDraft['scope'], before?: number) =>
    request<{ items: FeeRuleSaved[]; next_cursor: number | null }>(
      `/shops/${shop}/fee-rules?data_identity=${scope.data_identity}&channel=${scope.channel}${before ? `&before=${before}` : ''}`,
    ),
  get: (shop: number, id: number) => request<FeeRuleSaved>(`/shops/${shop}/fee-rules/${id}`),
  preview: (shop: number, body: FeeRuleDraft) =>
    request<FeeRulePreview>(`/shops/${shop}/fee-rules/preview`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  write: (shop: number, body: FeeRuleWrite) =>
    request<FeeRuleSaved>(`/shops/${shop}/fee-rules`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  control: (
    shop: number,
    id: number,
    action: 'withdraw' | 'clear',
    body: {
      request_id: string
      version: number
      confirm: true
    },
  ) =>
    request<FeeRuleSaved>(`/shops/${shop}/fee-rules/${id}/${action}`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}
