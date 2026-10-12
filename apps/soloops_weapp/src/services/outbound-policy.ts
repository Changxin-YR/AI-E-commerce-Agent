// route: /outbound
import type { SourceReference } from './scope-types'

export interface MailChannel {
  provider: string
  configured: boolean
  id: number | null
  status: string
  sender: string
  recipient: string
  receipt_id: string | null
  verified_at: string | null
  verification_expires_at: string | null
  verification_subject: string
  verification_template: string
}
export interface MailApproval {
  id: number
  mode: string
  status: string
  max_uses: number
  used_count: number
  expires_at: string
  created_at: string
}
export interface OutboundMail {
  id: number
  shop_id: number
  channel_id: number
  provider: string
  smtp_message_id: string | null
  run_id: number
  sender: string
  recipient: string
  subject: string | null
  body: string | null
  content_hash: string
  status: string
  source_status: string
  channel_status: string
  version: number
  risk: string
  max_submissions: number
  dispatch_at: string | null
  receipt_id: string | null
  provider_event: string
  checked_at: string | null
  received_at: string | null
  receipt_evidence: string | null
  created_at: string
  approvals: MailApproval[]
}
export interface MailPage {
  items: OutboundMail[]
  next_before_id: number | null
}
export interface MailEvidence {
  content_hash: string
  sender: string
  recipient: string
  subject: string | null
  body: string | null
  version: number
  source: SourceReference | null
}
export const mailLabels: Record<string, string> = {
  not_configured: '未配置',
  disconnected: '尚未连接',
  verifying: '等待邮箱验证码',
  active: '已验证 / 有效',
  configuration_changed: '配置已变化',
  domain_unverified: '发送域未验证',
  sender_unverified: '发件账号验证未通过，请检查 SMTP 服务和授权码',
  smtp_accepted: 'QQ SMTP 已接受（250）',
  expired: '已过期',
  locked: '验证次数用尽',
  revoked: '已撤销',
  draft: '等待 R2 审批',
  sending: '提交中',
  unknown: '结果未知，请回查',
  accepted: '通道已接受',
  rejected: '通道已拒绝',
  cancelled: '已取消',
  used: '已消耗',
  invalidated: '已失效',
  channel_unavailable: '通道不可用',
  current: '来源有效',
  stale: '来源已变化',
  cleared: '正文已清除',
  submitted: '已取得提交回执',
  sent: '通道已发出',
  delivered: '通道报告送达',
  bounced: '退信',
  failed: '发送失败',
  complained: '投诉',
  delivery_delayed: '投递延迟',
}
export function mailLabel(value: string): string {
  return mailLabels[value] || value
}
export function activeApproval(item: OutboundMail): MailApproval | undefined {
  return item.approvals.find((grant) => grant.status === 'active')
}
// The server owns these gates; the client mirrors them so it never offers a
// write the service would refuse.
export function mailActions(item: OutboundMail) {
  const known = [
    'draft',
    'sending',
    'unknown',
    'accepted',
    'rejected',
    'cancelled',
  ].includes(item.status)
  const current = item.source_status === 'current'
  const editable =
    known && current && item.status === 'draft' && !item.dispatch_at
  const dispatchable = known && current && !item.dispatch_at
  const received =
    current &&
    item.body !== null &&
    (item.status === 'accepted' ||
      (item.provider === 'qq_smtp' && item.status === 'unknown'))
  return {
    edit: editable,
    reject: editable,
    approve: editable && item.channel_status === 'active',
    dispatch: dispatchable && !!activeApproval(item),
    revoke: !!activeApproval(item) && item.status !== 'cancelled',
    reconcile: dispatchable && item.status !== 'sending' && item.body !== null,
    receipt: received,
  }
}
export function verificationCode(value: string): string {
  const code = value.trim()
  if (!/^[0-9]{8}$/.test(code)) throw new Error('邮箱验证码须为 8 位数字。')
  return code
}
export function approvalHours(value: number | string): number {
  const hours = Number(value)
  if (!Number.isInteger(hours) || hours < 1 || hours > 24)
    throw new Error('预授权有效小时须为 1–24 的整数。')
  return hours
}
export function recipientAddress(value: string): string | undefined {
  const address = value.trim()
  if (!address) return undefined
  if (address.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address))
    throw new Error('收件地址格式无效。')
  if ([...address].some((c) => c.charCodeAt(0) < 32 || c.charCodeAt(0) === 127))
    throw new Error('收件地址不能包含控制字符或换行。')
  return address
}
export function mailEdit(subject: string, body: string) {
  const cleanSubject = subject.replace(/[\r\n]/g, ' ').trim()
  if (!cleanSubject || cleanSubject.length > 200)
    throw new Error('邮件主题须为 1–200 字且不含换行。')
  const cleanBody = body.trim()
  if (!cleanBody || cleanBody.length > 12000)
    throw new Error('邮件全文须为 1–12000 字。')
  return { subject: cleanSubject, body: cleanBody }
}
export function receiptEvidence(value: string): string {
  const evidence = value.trim()
  if (evidence.length < 5 || evidence.length > 500)
    throw new Error('实际收件证据须为 5–500 字。')
  return evidence
}
export function receiptId(value: string): string | null {
  const id = value.trim()
  if (!id) return null
  if (!/^[0-9a-fA-F-]{36}$/.test(id)) throw new Error('通道邮件标识须为 UUID。')
  return id
}
export function createRecipient(
  provider: string,
  value: string,
): string | undefined {
  return provider === 'qq_smtp' ? recipientAddress(value) : undefined
}
export function mailEvidence(item: OutboundMail): MailEvidence {
  return {
    content_hash: item.content_hash,
    sender: item.sender,
    recipient: item.recipient,
    subject: item.subject,
    body: item.body,
    version: item.version,
    source: null,
  }
}
