import { request } from './client'
import type { QualityPage, QualityResult, QualitySaved, QualityScope } from '@/types/productQuality'

const root = (shop: number) => `/shops/${shop}/product-quality`
export const productQualityApi = {
  preview: (shop: number, scope: QualityScope) =>
    request<QualityResult>(`${root(shop)}/preview`, {
      method: 'POST',
      body: JSON.stringify(scope),
    }),
  save: (result: QualityResult, requestId: string) =>
    request<QualitySaved>(`${root(result.shop_id)}/reports`, {
      method: 'POST',
      body: JSON.stringify({
        scope: result.scope,
        expected_revision: result.source_revision,
        expected_preview_hash: result.preview_hash,
        request_id: requestId,
        confirm: true,
      }),
    }),
  list: (shop: number, before?: number) =>
    request<QualityPage>(`${root(shop)}/reports${before ? `?before=${before}` : ''}`),
  get: (shop: number, id: number) => request<QualitySaved>(`${root(shop)}/reports/${id}`),
  clear: (shop: number, id: number) =>
    request<QualitySaved>(`${root(shop)}/reports/${id}/clear`, {
      method: 'POST',
      body: JSON.stringify({ confirm: true }),
    }),
}
