// H15 结算与回款（web_route: /settlements）页面私有纯逻辑。
// 只放可离线测试的校验/派生逻辑，不放请求，不依赖 Taro 或会话。
import type { SourceReference } from './scope-types'

export type DataIdentity = 'user_import' | 'synthetic'
export type SourceChannel = 'generic' | 'shopify' | 'amazon' | 'other'
export type ControlAction = 'withdraw' | 'clear'
export type RecordStatus = 'active' | 'stale' | 'withdrawn' | 'cleared'

export interface SettlementScope {
  data_identity: DataIdentity
  channel: SourceChannel
  start_at: string
  end_at: string
  timezone: string
}

export interface ManualReceipt {
  payout_ref: string
  receipt_ref: string
  amount: string
  currency: string
  received_at: string
  timezone: string
  note: string
}

export interface SettlementContent {
  statement_id: string
  note: string
  receipts: ManualReceipt[]
}

export interface SettlementStatementItem {
  id: number
  statement_id: string
  line_id: string
  entry_type: 'sale' | 'refund' | 'fee' | 'payout'
  amount: string
  currency: string
  occurred_at: string
  evidence_ref: string
  fee_name: string
  settlement_id: string
  order_id: string
  note: string
  source: SourceReference
}

export interface SettlementTotal {
  currency: string
  entry_type: string
  amount: string
  count: number
}

export interface PayoutComparison {
  payout_ref: string
  status:
    | 'matched'
    | 'amount_difference'
    | 'statement_only'
    | 'receipt_only'
    | 'ambiguous'
    | 'currency_mismatch'
    | 'missing_reference'
  statement_ids: number[]
  receipt_indexes: number[]
  difference: string | null
}

export interface SettlementSnapshot {
  scope: SettlementScope
  content: SettlementContent
  source_revision: number
  calculated_at: string
  statements: SettlementStatementItem[]
  totals: SettlementTotal[]
  comparisons: PayoutComparison[]
  outside_cycle_ids: number[]
  coverage_status: 'unknown'
  balance_status: 'unknown'
  bank_status: 'unverified'
  checks: string[]
}

export interface SettlementPreview {
  preview_hash: string
  snapshot: SettlementSnapshot
}

export interface SettlementHistoryEntry {
  version: number
  action: string
  has_content: boolean
  created_at: string
}

export interface SettlementSaved {
  id: number
  shop_id: number
  data_identity: DataIdentity
  channel: SourceChannel
  status: RecordStatus
  version: number
  content_version: number
  created_at: string
  snapshot: SettlementSnapshot | null
  history: SettlementHistoryEntry[]
}

export interface SettlementPage {
  items: SettlementSaved[]
  next_cursor: number | null
}

export interface SettlementCurrent {
  record: SettlementSaved
  preview: SettlementPreview | null
}

export interface SettlementDraftBody {
  scope: SettlementScope
  settlement_id: number | null
  version: number
  content: SettlementContent
}

export interface SettlementWriteBody extends SettlementDraftBody {
  preview_hash: string
  request_id: string
  confirm: true
}

export interface SettlementControlBody {
  request_id: string
  version: number
  confirm: true
}

export const identities: DataIdentity[] = ['user_import', 'synthetic']
export const channels: SourceChannel[] = [
  'generic',
  'shopify',
  'amazon',
  'other',
]
export const currencies = [
  'USD',
  'CNY',
  'EUR',
  'GBP',
  'JPY',
  'CAD',
  'AUD',
  'HKD',
  'SGD',
]
export const settlementStatuses: Record<string, string> = {
  active: '有效 · 保存时依据一致',
  stale: '来源变化 · 待重核',
  withdrawn: '已撤销 · 保留历史',
  cleared: '正文已清除',
}
export const revisionActions: Record<string, string> = {
  create: '新建',
  update: '修订',
  withdraw: '撤销',
  clear: '清除',
}
export const statEntryTypes: Record<string, string> = {
  sale: '销售款',
  refund: '退款',
  fee: '费用',
  payout: '平台记载回款',
  manual_receipt: '人工到账声明',
}
export const payoutStatuses: Record<string, string> = {
  matched: '金额一致 · 凭据已核验未及银行',
  amount_difference: '金额差异 · 待核',
  statement_only: '仅平台记载 · 缺少人工到账登记',
  receipt_only: '仅人工登记 · 缺少平台记载',
  ambiguous: '重复凭据 · 整组待核',
  currency_mismatch: '币种不一致 · 不换汇',
  missing_reference: '平台回款缺少凭据号 · 无法比对',
}
export const controls: Record<ControlAction, string> = {
  withdraw: '撤销 · 释放账单与凭据占用并保留历史',
  clear: '清除 · 擦除全部历史正文与依据',
}
export const maxReceipts = 50
export const settlementsPerPage = 20

// 与服务端一致的显式偏移时间字符串，例如 2026-10-12T09:30:00+08:00。
const INSTANT =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d{1,9})?(Z|[+-]\d{2}:\d{2})$/
const MONEY = /^\d+(?:\.\d{1,4})?$/
const MONEY_LIMIT = '100000000'

function text(value: string, label: string, max: number): string {
  const trimmed = value.trim()
  if (!trimmed || trimmed.length > max)
    throw new Error(`${label}须为 1–${max} 个字符。`)
  return trimmed
}
export function checkedTimezone(value: string, label = '时区'): string {
  const zone = value.trim()
  try {
    new Intl.DateTimeFormat('en', { timeZone: zone })
  } catch {
    throw new Error(`${label}无效，请填写 IANA 时区，例如 Asia/Shanghai。`)
  }
  return zone
}
export function zoneOffsetMinutes(date: Date, timezone: string): number {
  const rendered = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date)
  const parts = /(\d{4})-(\d{2})-(\d{2}),?\s*(\d{1,2}):(\d{2}):(\d{2})/.exec(
    rendered,
  )
  if (!parts)
    throw new Error(
      '时区换算失败，请手工填写带偏移的时间，例如 UTC 的 2026-10-12T09:30:00Z。',
    )
  const asUtc = Date.UTC(
    Number(parts[1]),
    Number(parts[2]) - 1,
    Number(parts[3]),
    Number(parts[4]),
    Number(parts[5]),
    Number(parts[6]),
  )
  return Math.round((asUtc - date.getTime()) / 60000)
}
// 偏移显式写在文本里，服务端会按 IANA 时区复核；不用本地 Date 推断生成偏移。
export function localIso(date: Date, timezone: string): string {
  const offset = zoneOffsetMinutes(date, timezone)
  const shifted = new Date(date.getTime() + offset * 60000)
  const sign = offset < 0 ? '-' : '+'
  const absolute = Math.abs(offset)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${shifted.toISOString().slice(0, 19)}${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`
}
function explicitOffset(value: string): number | null {
  if (value === 'Z') return null
  const match = /^([+-])(\d{2}):(\d{2})$/.exec(value)
  if (!match) return null
  const minutes = Number(match[2]) * 60 + Number(match[3])
  return match[1] === '-' ? -minutes : minutes
}
export function checkedInstant(
  value: string,
  label: string,
  timezone: string,
): string {
  const instant = value.trim()
  const match = INSTANT.exec(instant)
  if (!match)
    throw new Error(
      `${label}须为带明确时区偏移的 ISO 时间，例如 2026-10-12T09:30:00+08:00 或 2026-10-12T01:30:00Z。`,
    )
  const parsed = Date.parse(instant)
  if (!Number.isFinite(parsed)) throw new Error(`${label}不是有效时间。`)
  const year = Number(match[1])
  if (year < 2000 || year > 2100)
    throw new Error(`${label}年份须在 2000—2100 之间。`)
  // 明确写出的偏移必须与所选 IANA 时区一致；Z 表示同一时刻，不做偏移换算。
  // match[7] 是显式偏移（Z 或 ±HH:MM）。
  const offset = explicitOffset(match[7] ?? '')
  if (
    offset !== null &&
    offset !== zoneOffsetMinutes(new Date(parsed), timezone)
  )
    throw new Error(`${label}的偏移与所选 IANA 时区不符，请按该时区重新填写。`)
  return instant
}
export function checkedScope(raw: SettlementScope): SettlementScope {
  if (!identities.includes(raw.data_identity)) throw new Error('数据身份无效。')
  if (!channels.includes(raw.channel)) throw new Error('来源渠道无效。')
  const timezone = checkedTimezone(raw.timezone, '周期显示时区')
  const start = checkedInstant(raw.start_at, '周期开始', timezone)
  const end = checkedInstant(raw.end_at, '周期结束', timezone)
  const duration = Date.parse(end) - Date.parse(start)
  if (duration <= 0 || duration > 366 * 86400000)
    throw new Error('周期须大于零且不超过 366 天，包含开始、不含结束。')
  return {
    data_identity: raw.data_identity,
    channel: raw.channel,
    start_at: start,
    end_at: end,
    timezone,
  }
}
function digits(value: string): string {
  return value.replace(/^0+/, '') || '0'
}
function greaterThan(value: string, limit: string): boolean {
  const [head, tail = ''] = value.split('.')
  const [limitHead, limitTail = ''] = limit.split('.')
  const left = digits(head)
  const right = digits(limitHead)
  if (left.length !== right.length) return left.length > right.length
  if (left !== right) return left > right
  const width = Math.max(tail.length, limitTail.length)
  return tail.padEnd(width, '0') > limitTail.padEnd(width, '0')
}
function money(value: string, label: string, positive = false): string {
  const trimmed = value.trim()
  if (!MONEY.test(trimmed))
    throw new Error(`${label}须为最多四位小数的金额字符串。`)
  if (greaterThan(trimmed, MONEY_LIMIT))
    throw new Error(`${label}不能超过 ${MONEY_LIMIT}。`)
  if (positive && !/[1-9]/.test(trimmed))
    throw new Error(`${label}必须大于零；冲正请修订或撤销原登记。`)
  return trimmed
}
export function checkedReceipt(raw: ManualReceipt): ManualReceipt {
  const timezone = checkedTimezone(raw.timezone, '到账显示时区')
  const currency = raw.currency.trim().toUpperCase()
  if (!/^[A-Z]{3}$/.test(currency))
    throw new Error('到账币种须为三位字母代码；本页不换汇。')
  return {
    payout_ref: text(raw.payout_ref, '平台回款凭据号', 120),
    receipt_ref: text(raw.receipt_ref, '人工到账凭据号', 120),
    amount: money(raw.amount, '到账金额', true),
    currency,
    received_at: checkedInstant(raw.received_at, '到账时间', timezone),
    timezone,
    note: text(raw.note, '凭据核验说明', 500),
  }
}
export function receiptKeys(receipts: ManualReceipt[]): string[] {
  return receipts.map((item) =>
    item.receipt_ref.normalize('NFKC').trim().toLowerCase(),
  )
}
export function checkedContent(raw: SettlementContent): SettlementContent {
  if (raw.receipts.length > maxReceipts)
    throw new Error(`每份登记最多 ${maxReceipts} 笔人工到账凭据。`)
  const receipts = raw.receipts.map(checkedReceipt)
  const keys = receiptKeys(receipts)
  if (new Set(keys).size !== keys.length)
    throw new Error('同一人工到账凭据不能重复登记。')
  return {
    statement_id: text(raw.statement_id, '原账单号', 120),
    note: text(raw.note, '周期依据与核对说明', 1000),
    receipts,
  }
}
export function checkedDraft(raw: SettlementDraftBody): SettlementDraftBody {
  const settlementId = raw.settlement_id
  if (settlementId !== null) {
    if (!Number.isInteger(settlementId) || settlementId <= 0)
      throw new Error('结算登记编号无效，请重新读取记录。')
  }
  if (!Number.isInteger(raw.version) || raw.version < 0)
    throw new Error('结算登记版本无效，请重新读取记录。')
  if (settlementId === null && raw.version !== 0)
    throw new Error('新建登记版本必须为零，请重新开始。')
  return {
    scope: checkedScope(raw.scope),
    settlement_id: settlementId,
    version: raw.version,
    content: checkedContent(raw.content),
  }
}
// 服务端只接受 withdraw / clear；cleared 记录无可用处理动作。
export function availableActions(status: string): ControlAction[] {
  if (status === 'active' || status === 'stale') return ['withdraw', 'clear']
  if (status === 'withdrawn') return ['clear']
  return []
}
export function controlBody(
  version: number,
  request: string,
): SettlementControlBody {
  if (!Number.isInteger(version) || version < 1)
    throw new Error('结算登记版本无效，请重新读取记录。')
  return { request_id: request, version, confirm: true }
}
export function isCurrentVersion(
  saved: Pick<SettlementSaved, 'content_version'>,
  shown: number | null,
): boolean {
  return shown === saved.content_version
}
export function canEdit(saved: SettlementSaved): boolean {
  return (
    (saved.status === 'active' || saved.status === 'stale') &&
    saved.snapshot !== null
  )
}
export function emptySettlementScope(
  timezone = 'Asia/Shanghai',
  now: Date = new Date(),
): SettlementScope {
  const start = new Date(now.getTime() - 30 * 86400000)
  return {
    data_identity: 'user_import',
    channel: 'generic',
    start_at: localIso(start, timezone),
    end_at: localIso(now, timezone),
    timezone,
  }
}
export function emptySettlementContent(): SettlementContent {
  return { statement_id: '', note: '', receipts: [] }
}
export function emptyReceipt(
  currency = 'USD',
  timezone = 'UTC',
  now: Date = new Date(),
): ManualReceipt {
  return {
    payout_ref: '',
    receipt_ref: '',
    amount: '',
    currency,
    received_at: localIso(now, timezone),
    timezone,
    note: '',
  }
}
export function trimmedAmount(value: string | null | undefined): string {
  if (value == null || value === '') return '未知'
  return value.includes('.')
    ? value.replace(/0+$/, '').replace(/\.$/, '')
    : value
}
export function statusCounts(
  values: string[],
): { key: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1)
  return [...counts.entries()]
    .map(([key, count]) => ({ key, count }))
    .sort((left, right) => left.key.localeCompare(right.key))
}
// 契约动作 ID 常量：便于与 contracts/ui-contract.json 逐条对照。
export const settlementActionIds = {
  preview: 'preview_api_shops__shop_id__settlements_preview_post',
  write: 'write_api_shops__shop_id__settlements_post',
  page: 'page_api_shops__shop_id__settlements_get',
  get: 'get_api_shops__shop_id__settlements__settlement_id__get',
  current:
    'read_current_api_shops__shop_id__settlements__settlement_id__current_get',
  control:
    'control_api_shops__shop_id__settlements__settlement_id___action__post',
} as const
export const settlementRouteQueries = {
  preview: 'POST /shops/{shop_id}/settlements/preview',
  write: 'POST /shops/{shop_id}/settlements',
  page: 'GET /shops/{shop_id}/settlements',
  get: 'GET /shops/{shop_id}/settlements/{settlement_id}',
  current: 'GET /shops/{shop_id}/settlements/{settlement_id}/current',
  control: 'POST /shops/{shop_id}/settlements/{settlement_id}/{action}',
} as const
