import { request } from './client'
import type {
  AnalysisResult,
  AnalysisScope,
  SavedAnalysis,
  SourceDetail,
  CostHistory,
  CostWrite,
} from '@/types/analytics'

const base = (shop: number) => `/shops/${shop}/analytics`
export const analyticsApi = {
  costHistory: (shop: number, row: number) =>
    request<CostHistory>(`${base(shop)}/order-costs/${row}`),
  writeCost: (shop: number, row: number, data: CostWrite) =>
    request<CostHistory>(`${base(shop)}/order-costs/${row}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  revision: (shop: number) => request<number>(`${base(shop)}/revision`),
  getSaved: (shop: number, id: number) => request<SavedAnalysis>(`${base(shop)}/saved/${id}`),
  calculate: (shop: number, scope: AnalysisScope) =>
    request<AnalysisResult>(`${base(shop)}/calculate`, {
      method: 'POST',
      body: JSON.stringify(scope),
    }),
  ask: (shop: number, scope: AnalysisScope, question: string) =>
    request<AnalysisResult>(`${base(shop)}/ask`, {
      method: 'POST',
      body: JSON.stringify({ scope, question }),
    }),
  save: (shop: number, result: AnalysisResult) =>
    request<SavedAnalysis>(`${base(shop)}/saved`, {
      method: 'POST',
      body: JSON.stringify({ scope: result.scope, expected_revision: result.source_revision }),
    }),
  saved: (shop: number) => request<SavedAnalysis[]>(`${base(shop)}/saved`),
  todo: (shop: number, id: number) =>
    request<SavedAnalysis>(`${base(shop)}/saved/${id}/todo`, { method: 'POST' }),
  changeTodo: (shop: number, item: SavedAnalysis, action: 'complete' | 'reopen') =>
    request<SavedAnalysis>(`${base(shop)}/saved/${item.id}/todo/action`, {
      method: 'POST',
      body: JSON.stringify({ expected_version: item.todo!.version, action }),
    }),
  source: (shop: number, row: number) => request<SourceDetail>(`${base(shop)}/sources/${row}`),
}
