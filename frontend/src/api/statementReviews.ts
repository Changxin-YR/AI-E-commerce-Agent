import { request } from './client'
import type {
  ReviewCurrent,
  ReviewDraft,
  ReviewPreview,
  ReviewSaved,
  ReviewWrite,
} from '@/types/statementReviews'

export const statementReviewsApi = {
  list: (shop: number, scope: ReviewDraft['scope'], before?: number) =>
    request<{ items: ReviewSaved[]; next_cursor: number | null }>(
      `/shops/${shop}/statement-reviews?data_identity=${scope.data_identity}&channel=${scope.channel}${before ? `&before=${before}` : ''}`,
    ),
  get: (shop: number, id: number, version?: number) =>
    request<ReviewSaved>(
      `/shops/${shop}/statement-reviews/${id}${version ? `?version=${version}` : ''}`,
    ),
  current: (shop: number, id: number) =>
    request<ReviewCurrent>(`/shops/${shop}/statement-reviews/${id}/current`),
  preview: (shop: number, body: ReviewDraft) =>
    request<ReviewPreview>(`/shops/${shop}/statement-reviews/preview`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  write: (shop: number, body: ReviewWrite) =>
    request<ReviewSaved>(`/shops/${shop}/statement-reviews`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  control: (
    shop: number,
    id: number,
    action: 'withdraw' | 'clear',
    body: { request_id: string; version: number; confirm: true },
  ) =>
    request<ReviewSaved>(`/shops/${shop}/statement-reviews/${id}/${action}`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}
