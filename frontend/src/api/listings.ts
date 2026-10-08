import { request } from './client'
import type {
  ListingContent,
  ListingVersion,
  ProductFacts,
  ProductWorkspace,
} from '@/types/listings'

const base = (shop: number) => `/shops/${shop}/listings`
export const listingsApi = {
  products: (shop: number, query: string, offset: number) =>
    request<ProductFacts[]>(
      `${base(shop)}/products?q=${encodeURIComponent(query)}&offset=${offset}`,
    ),
  workspace: (shop: number, product: number) =>
    request<ProductWorkspace>(`${base(shop)}/products/${product}`),
  history: (shop: number) => request<ListingVersion[]>(`${base(shop)}/versions`),
  get: (shop: number, id: number) => request<ListingVersion>(`${base(shop)}/versions/${id}`),
  generate: (shop: number, workspace: ProductWorkspace) =>
    request<ListingVersion>(`${base(shop)}/generate`, {
      method: 'POST',
      body: JSON.stringify({
        product_id: workspace.product.product_id,
        expected_source_row_id: workspace.product.source.row_id,
        expected_active_id: workspace.active_id,
      }),
    }),
  revise: (shop: number, item: ListingVersion, active: number | null, content: ListingContent) =>
    request<ListingVersion>(`${base(shop)}/versions/${item.id}/revise`, {
      method: 'POST',
      body: JSON.stringify({ expected_version: item.version, expected_active_id: active, content }),
    }),
  decide: (
    shop: number,
    item: ListingVersion,
    decision: 'approve' | 'reject',
    confirmed: boolean,
  ) =>
    request<ListingVersion>(`${base(shop)}/versions/${item.id}/decision`, {
      method: 'POST',
      body: JSON.stringify({
        expected_version: item.version,
        decision,
        facts_confirmed: confirmed,
      }),
    }),
}
