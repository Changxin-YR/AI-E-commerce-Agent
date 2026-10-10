import { request } from './client'
import type { MailChannel, OutboundMail } from '@/types/outbound'
const root = (shop: number) => `/shops/${shop}/outbound`
const post = <T>(path: string, data: unknown = {}) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(data) })
export const outboundApi = {
  channel: (shop: number) => request<MailChannel>(`${root(shop)}/channel`),
  connect: (shop: number) =>
    post<MailChannel>(`${root(shop)}/channel/connect`, { confirmed: true }),
  verify: (shop: number, id: number, code: string) =>
    post<MailChannel>(`${root(shop)}/channel/${id}/verify`, { code }),
  disconnect: (shop: number, id: number) => post<MailChannel>(`${root(shop)}/channel/${id}/revoke`),
  list: (shop: number, before?: number) =>
    request<{ items: OutboundMail[]; next_before_id: number | null }>(
      `${root(shop)}/messages${before ? `?before_id=${before}` : ''}`,
    ),
  create: (shop: number, run: number, recipient?: string) =>
    post<OutboundMail>(`${root(shop)}/messages`, { run_id: run, recipient }),
  get: (shop: number, id: number) => request<OutboundMail>(`${root(shop)}/messages/${id}`),
  edit: (mail: OutboundMail, subject: string, body: string) =>
    request<OutboundMail>(`${root(mail.shop_id)}/messages/${mail.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ version: mail.version, subject, body }),
    }),
  approve: (mail: OutboundMail, mode: 'once' | 'preauthorized', hours: number) =>
    post<OutboundMail>(`${root(mail.shop_id)}/messages/${mail.id}/approve`, {
      version: mail.version,
      mode,
      valid_hours: hours,
      confirmed: true,
    }),
  revoke: (mail: OutboundMail, approval: number) =>
    post<OutboundMail>(`${root(mail.shop_id)}/messages/${mail.id}/approvals/${approval}/revoke`),
  send: (mail: OutboundMail, approval: number) =>
    post<OutboundMail>(`${root(mail.shop_id)}/messages/${mail.id}/send`, {
      version: mail.version,
      approval_id: approval,
    }),
  reject: (mail: OutboundMail) =>
    post<OutboundMail>(`${root(mail.shop_id)}/messages/${mail.id}/reject`, {
      version: mail.version,
    }),
  reconcile: (mail: OutboundMail, receipt: string) =>
    post<OutboundMail>(`${root(mail.shop_id)}/messages/${mail.id}/reconcile`, {
      receipt_id: receipt || null,
    }),
  receipt: (mail: OutboundMail, evidence: string) =>
    post<OutboundMail>(`${root(mail.shop_id)}/messages/${mail.id}/receipt`, {
      confirmed: true,
      evidence,
    }),
}
