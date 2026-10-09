import { request } from './client'
import type {
  SettlementCurrent,
  SettlementDraft,
  SettlementPreview,
  SettlementSaved,
  SettlementWrite,
} from '@/types/settlements'

export const settlementsApi = {
  list: (shop: number, scope: SettlementDraft['scope'], before?: number) =>
    request<{ items: SettlementSaved[]; next_cursor: number | null }>(
      `/shops/${shop}/settlements?data_identity=${scope.data_identity}&channel=${scope.channel}${before ? `&before=${before}` : ''}`,
    ),
  get: (shop: number, id: number, version?: number) =>
    request<SettlementSaved>(
      `/shops/${shop}/settlements/${id}${version ? `?version=${version}` : ''}`,
    ),
  current: (shop: number, id: number) =>
    request<SettlementCurrent>(`/shops/${shop}/settlements/${id}/current`),
  preview: (shop: number, body: SettlementDraft) =>
    request<SettlementPreview>(`/shops/${shop}/settlements/preview`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  write: (shop: number, body: SettlementWrite) =>
    request<SettlementSaved>(`/shops/${shop}/settlements`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  control: (
    shop: number,
    id: number,
    action: 'withdraw' | 'clear',
    body: { request_id: string; version: number; confirm: true },
  ) =>
    request<SettlementSaved>(`/shops/${shop}/settlements/${id}/${action}`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}
