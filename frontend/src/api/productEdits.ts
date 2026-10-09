import { request } from './client'
import type { EditAction, EditCreate, EditSaved } from '@/types/productEdits'

const root = (shop: number) => `/shops/${shop}/product-edits`
export const productEditsApi = {
  create: (shop: number, data: EditCreate) =>
    request<EditSaved>(root(shop), { method: 'POST', body: JSON.stringify(data) }),
  get: (shop: number, id: number) => request<EditSaved>(`${root(shop)}/${id}`),
  list: (shop: number, before?: number) =>
    request<{ items: EditSaved[]; next_cursor: number | null }>(
      `${root(shop)}${before ? `?before=${before}` : ''}`,
    ),
  decide: (edit: EditSaved, action: EditAction) =>
    request<EditSaved>(`${root(edit.shop_id)}/${edit.id}/${action}`, {
      method: 'POST',
      body: JSON.stringify({
        version: edit.version,
        confirm: true,
        ...(action === 'approve' ? { expected_preview_hash: edit.preview_hash } : {}),
      }),
    }),
}
