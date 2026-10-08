import { request } from './client'
import type {
  MessageFacts,
  Policy,
  PolicyData,
  ReplyDraft,
  SupportWorkspace,
} from '@/types/support'

const root = (shop: number) => `/shops/${shop}/support`
const post = <T>(url: string, data: unknown) =>
  request<T>(url, { method: 'POST', body: JSON.stringify(data) })
export const supportApi = {
  messages: (shop: number, q = '', offset = 0) =>
    request<MessageFacts[]>(
      `${root(shop)}/messages?${new URLSearchParams({ q, offset: String(offset) })}`,
    ),
  workspace: (shop: number, id: number) =>
    request<SupportWorkspace>(`${root(shop)}/messages/${id}`),
  policies: (shop: number, q = '', offset = 0) =>
    request<Policy[]>(
      `${root(shop)}/policies?${new URLSearchParams({ q, offset: String(offset) })}`,
    ),
  savePolicy: (shop: number, data: PolicyData, expected: number | null) =>
    post<Policy>(`${root(shop)}/policies`, { data, expected_policy_id: expected }),
  clearPolicy: (shop: number, id: number) => post<Policy>(`${root(shop)}/policies/${id}/clear`, {}),
  history: (shop: number) => request<ReplyDraft[]>(`${root(shop)}/drafts`),
  get: (shop: number, id: number) => request<ReplyDraft>(`${root(shop)}/drafts/${id}`),
  generate: (shop: number, workspace: SupportWorkspace, verified: boolean, policies: number[]) =>
    post<ReplyDraft>(`${root(shop)}/messages/${workspace.message.id}/generate`, {
      expected_source_row_id: workspace.message.source.row_id,
      expected_order_row_ids: verified ? workspace.orders.map((o) => o.source.row_id) : [],
      order_verified: verified,
      policy_ids: policies,
    }),
  edit: (shop: number, draft: ReplyDraft, reply: string) =>
    post<ReplyDraft>(`${root(shop)}/drafts/${draft.id}/edit`, {
      expected_version: draft.version,
      reply,
    }),
  act: (shop: number, draft: ReplyDraft, action: 'handoff' | 'archive' | 'reopen') =>
    post<ReplyDraft>(`${root(shop)}/drafts/${draft.id}/action`, {
      expected_version: draft.version,
      action,
    }),
}
