export interface MailChannel {
  provider: 'resend' | 'qq_smtp'
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
  max_uses: 1
  used_count: number
  expires_at: string
  created_at: string
}
export interface OutboundMail {
  provider: 'resend' | 'qq_smtp'
  smtp_message_id: string | null
  id: number
  shop_id: number
  channel_id: number
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
  risk: 'R2'
  max_submissions: 1
  dispatch_at: string | null
  receipt_id: string | null
  provider_event: string
  checked_at: string | null
  received_at: string | null
  receipt_evidence: string | null
  created_at: string
  approvals: MailApproval[]
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
  current: '当前来源',
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
