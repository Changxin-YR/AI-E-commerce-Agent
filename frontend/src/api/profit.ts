import { request } from './client'
import type { SavedStudy, SavedStudySummary, StudyInput, StudyResult } from '@/types/profit'

const base = (shop: number) => `/shops/${shop}/profit`
export const profitApi = {
  calculate: (shop: number, input: StudyInput) =>
    request<StudyResult>(`${base(shop)}/calculate`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  save: (shop: number, input: StudyInput, requestKey: string) =>
    request<SavedStudy>(`${base(shop)}/saved`, {
      method: 'POST',
      body: JSON.stringify({ ...input, request_key: requestKey }),
    }),
  list: (shop: number, offset = 0) =>
    request<SavedStudySummary[]>(`${base(shop)}/saved?offset=${offset}`),
  get: (shop: number, id: number) => request<SavedStudy>(`${base(shop)}/saved/${id}`),
  clear: (shop: number, id: number) =>
    request<void>(`${base(shop)}/saved/${id}`, { method: 'DELETE' }),
}
