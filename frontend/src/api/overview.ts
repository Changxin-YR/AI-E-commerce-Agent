import { request } from './client'
import type { OverviewPage, OverviewResult, OverviewSaved, OverviewScope } from '@/types/overview'

export const overviewApi = {
  calculate: (scope: OverviewScope) =>
    request<OverviewResult>('/overview/calculate', { method: 'POST', body: JSON.stringify(scope) }),
  save: (result: OverviewResult, requestId: string) =>
    request<OverviewSaved>('/overview/reports', {
      method: 'POST',
      body: JSON.stringify({
        request_id: requestId,
        scope: result.scope,
        expected_revisions: Object.fromEntries(
          result.shops.map((s) => [s.shop_id, s.source_revision]),
        ),
      }),
    }),
  list: (before?: number) =>
    request<OverviewPage>(`/overview/reports${before ? `?before=${before}` : ''}`),
  get: (id: number) => request<OverviewSaved>(`/overview/reports/${id}`),
  clear: (id: number) =>
    request<OverviewSaved>(`/overview/reports/${id}/clear`, {
      method: 'POST',
      body: JSON.stringify({ confirm: true }),
    }),
}
