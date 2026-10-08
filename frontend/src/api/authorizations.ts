import { request } from './client'
import type { OperationScope } from '@/types/operations'
import type { AgentRun } from '@/types/agent'

export interface AuthorizationUse {
  id: number
  execution_id: number
  operation_run_id: number
  changes: { task_id: number; before: string; after: string; version: number }[]
  reused_count: number
  created_at: string
  reverted_at: string | null
}
export interface InternalAuthorization {
  id: number
  shop_id: number
  version: number
  origin_execution_id: number
  scope: OperationScope
  source_revision: number
  candidate_count: number
  max_uses: number
  used_count: number
  status: string
  expires_at: string
  source_valid_until: string | null
  revoked_at: string | null
  created_at: string
  uses: AuthorizationUse[]
}
interface AuthorizationPage {
  items: InternalAuthorization[]
  next_before_id: number | null
}
const root = (shop: number) => `/shops/${shop}/authorizations`
export const authorizationsApi = {
  get: (shop: number, id: number) => request<InternalAuthorization>(`${root(shop)}/${id}`),
  list: (shop: number, before?: number) =>
    request<AuthorizationPage>(`${root(shop)}${before ? `?before_id=${before}` : ''}`),
  create: (run: AgentRun, count: number, hours: number, requestId: string) =>
    request<InternalAuthorization>(root(run.shop_id), {
      method: 'POST',
      body: JSON.stringify({
        request_id: requestId,
        execution_id: run.id,
        expected_version: run.version,
        max_uses: count,
        valid_hours: hours,
        confirmed: true,
      }),
    }),
  revoke: (grant: InternalAuthorization) =>
    request<InternalAuthorization>(`${root(grant.shop_id)}/${grant.id}/revoke`, {
      method: 'POST',
      body: JSON.stringify({ version: grant.version }),
    }),
  revert: (grant: InternalAuthorization, useId: number) =>
    request<InternalAuthorization>(`${root(grant.shop_id)}/${grant.id}/uses/${useId}/revert`, {
      method: 'POST',
    }),
}
export const authorizationLabels: Record<string, string> = {
  active: '有效',
  revoked: '已撤销',
  expired: '已到期',
  exhausted: '次数已用尽',
  source_changed: '来源已变化或过期',
  rules_changed: '经营规则已变化',
}
