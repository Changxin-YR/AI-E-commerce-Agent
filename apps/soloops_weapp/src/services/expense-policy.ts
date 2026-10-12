// route: /expenses
import type { SourceReference } from './scope-types'

export type DataIdentity = 'user_import' | 'synthetic'
export type SourceChannel = 'generic' | 'shopify' | 'amazon' | 'other'
export type ExpenseCategory =
  | 'shipping'
  | 'packaging'
  | 'storage'
  | 'platform'
  | 'advertising'
  | 'tax'
  | 'other'
export type Allocation = 'shop' | 'order_line'
export type ControlAction = 'withdraw' | 'clear'

export interface ExpenseContent {
  label: string
  category: ExpenseCategory
  amount: string
  currency: string
  occurred_at: string
  timezone: string
  evidence_ref: string
  evidence_note: string
  allocation: Allocation
  order_line_id: number | null
  expected_source_row_id: number | null
  expected_source_revision: number | null
  reason: string
}
export interface ExpenseSnapshot {
  content: ExpenseContent
  source: SourceReference | null
  order_id: string | null
  line_id: string | null
  sku: string | null
  order_status: string | null
}
export interface ExpenseHistoryEntry {
  version: number
  action: string
  created_at: string
  snapshot: ExpenseSnapshot | null
}
export interface ExpenseSaved {
  id: number
  shop_id: number
  data_identity: DataIdentity
  channel: SourceChannel
  version: number
  status: 'active' | 'stale' | 'withdrawn' | 'cleared'
  created_at: string
  snapshot: ExpenseSnapshot | null
  history: ExpenseHistoryEntry[]
}
export interface ExpensePage {
  items: ExpenseSaved[]
  next_cursor: number | null
}
export interface ExpenseOrder {
  id: number
  order_id: string
  line_id: string
  sku: string
  currency: string
  status: string
  source: SourceReference
}
export interface ExpenseOrders {
  source_revision: number
  items: ExpenseOrder[]
}
export interface ExpenseScope {
  data_identity: DataIdentity
  channel: SourceChannel
  start_at: string
  end_at: string
  timezone: string
}
export interface ExpenseTotal {
  currency: string
  category: ExpenseCategory
  allocation: string
  amount: string
  count: number
}
export interface ExpenseSummary {
  scope: ExpenseScope
  totals: ExpenseTotal[]
  included_count: number
  stale_count: number
  withdrawn_count: number
  checks: string[]
}
export interface ExpenseWriteBody {
  request_id: string
  confirm: true
  data_identity: DataIdentity
  channel: SourceChannel
  version: number
  content: ExpenseContent
}
export interface ExpenseControlBody {
  request_id: string
  version: number
  confirm: true
}
export interface FeeRuleContent {
  fee_name: string
  category: ExpenseCategory
  reason: string
}
export interface FeeRuleHistoryEntry {
  version: number
  action: string
  content: FeeRuleContent | null
  created_at: string
}
export interface FeeRuleSaved {
  id: number
  shop_id: number
  data_identity: DataIdentity
  channel: SourceChannel
  status: 'active' | 'withdrawn' | 'cleared'
  version: number
  content: FeeRuleContent | null
  created_at: string
  history: FeeRuleHistoryEntry[]
}
export interface FeeRulePage {
  items: FeeRuleSaved[]
  next_cursor: number | null
}
export interface FeeMapping {
  statement_id: number
  status:
    | 'mapped'
    | 'unmapped'
    | 'ambiguous'
    | 'currency_mismatch'
    | 'category_conflict'
  category: ExpenseCategory | null
  rule_id: number | null
  rule_version: number | null
}
export interface FeeRuleChange {
  statement_id: number
  fee_name: string
  source: SourceReference
  before: FeeMapping
  after: FeeMapping
}
export interface FeeRuleDraftBody {
  scope: ExpenseScope
  rule_id: number | null
  version: number
  content: FeeRuleContent
}
export interface FeeRuleWriteBody extends FeeRuleDraftBody {
  preview_hash: string
  request_id: string
  confirm: true
}
export interface FeeRulePreview {
  preview_hash: string
  source_revision: number
  calculated_at: string
  previous: FeeRuleContent | null
  proposed: FeeRuleContent
  changes: FeeRuleChange[]
  statement_count: number
  scope: ExpenseScope
}

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
export const expenseCategories: Record<ExpenseCategory, string> = {
  shipping: '物流',
  packaging: '包装',
  storage: '仓储',
  platform: '平台服务',
  advertising: '广告',
  tax: '税费',
  other: '其他自定义费用',
}
export const expenseCategoryKeys = Object.keys(
  expenseCategories,
) as ExpenseCategory[]
export const expenseStatuses: Record<string, string> = {
  active: '已录入 · 账单待核对',
  stale: '来源变化 · 待重核',
  withdrawn: '已撤销',
  cleared: '正文已清除',
}
export const ruleStatuses: Record<string, string> = {
  active: '有效',
  withdrawn: '已撤销',
  cleared: '正文已清除',
}
export const revisionActions: Record<string, string> = {
  create: '录入',
  update: '修订',
  withdraw: '撤销',
  clear: '清除',
}
export const mappingStatuses: Record<string, string> = {
  mapped: '已按规则分类 · 业务待核',
  unmapped: '未匹配规则 · 待核',
  ambiguous: '重复凭据或规则 · 待核',
  currency_mismatch: '币种不一致 · 待核',
  category_conflict: '与人工费用类别冲突 · 待核',
}
export const controls: Record<ControlAction, string> = {
  withdraw: '撤销 · 保留历史，排除合计',
  clear: '清除 · 擦除全部历史正文与依据',
}
export const expensesPerPage = 20
export const rulesPerPage = 20

const MONEY = /^\d+(?:\.\d{1,4})?$/
const MONEY_LIMIT = '100000000'
const INSTANT =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d{1,9})?(Z|[+-]\d{2}:\d{2})$/

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
  const text = value.trim()
  if (!MONEY.test(text))
    throw new Error(`${label}须为最多四位小数的金额字符串。`)
  if (greaterThan(text, MONEY_LIMIT))
    throw new Error(`${label}不能超过 100000000。`)
  if (positive) {
    const [head, tail = ''] = text.split('.')
    if (digits(head) === '0' && !/[1-9]/.test(tail))
      throw new Error(`${label}必须大于零；费用冲正请撤销或修订原记录。`)
  }
  return text
}
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
// Offsets are explicit text so the server can verify them against the IANA zone.
export function localIso(date: Date, timezone: string): string {
  const offset = zoneOffsetMinutes(date, timezone)
  const shifted = new Date(date.getTime() + offset * 60000)
  const sign = offset < 0 ? '-' : '+'
  const absolute = Math.abs(offset)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${shifted.toISOString().slice(0, 19)}${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`
}
function offsetMinutes(value: string): number | null {
  if (value === 'Z') return 0
  const match = /^([+-])(\d{2}):(\d{2})$/.exec(value)
  if (!match) return null
  const minutes = Number(match[2]) * 60 + Number(match[3])
  return match[1] === '-' ? -minutes : minutes
}
function checkedInstant(
  value: string,
  label: string,
  timezone: string,
  maxYear = 2100,
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
  if (year < 2000 || year > maxYear)
    throw new Error(`${label}年份须在 2000—${maxYear} 之间。`)
  const offset = offsetMinutes(match[7] ?? '')
  if (offset === null) throw new Error(`${label}须包含明确时区偏移。`)
  if (offset !== zoneOffsetMinutes(new Date(parsed), timezone))
    throw new Error(`${label}的偏移与所选 IANA 时区不符，请按该时区重新填写。`)
  return instant
}
export function decimalText(value: string | null | undefined): string {
  if (value == null || value === '') return '未知'
  return value.includes('.')
    ? value.replace(/0+$/, '').replace(/\.$/, '')
    : value
}
export function emptyExpense(
  currency = 'USD',
  timezone = 'UTC',
  now: Date = new Date(),
): ExpenseContent {
  return {
    label: '',
    category: 'other',
    amount: '',
    currency,
    occurred_at: localIso(now, timezone),
    timezone,
    evidence_ref: '',
    evidence_note: '',
    allocation: 'shop',
    order_line_id: null,
    expected_source_row_id: null,
    expected_source_revision: null,
    reason: '',
  }
}
export function checkedExpenseContent(raw: ExpenseContent): ExpenseContent {
  const timezone = checkedTimezone(raw.timezone, '发生时区')
  const currency = raw.currency.trim().toUpperCase()
  if (!/^[A-Z]{3}$/.test(currency))
    throw new Error('费用币种须为三位字母代码；本页不换汇。')
  if (!expenseCategoryKeys.includes(raw.category))
    throw new Error('费用类别无效。')
  if (!['shop', 'order_line'].includes(raw.allocation))
    throw new Error('费用归属无效。')
  const orderLineId = raw.order_line_id
  const sourceRowId = raw.expected_source_row_id
  const sourceRevision = raw.expected_source_revision
  if (raw.allocation === 'order_line') {
    if (
      !Number.isInteger(orderLineId) ||
      (orderLineId ?? 0) <= 0 ||
      !Number.isInteger(sourceRowId) ||
      (sourceRowId ?? 0) <= 0 ||
      !Number.isInteger(sourceRevision) ||
      (sourceRevision ?? -1) < 0
    )
      throw new Error('订单行费用须先查找并绑定当前来源行与店铺来源版本。')
  } else if (
    orderLineId != null ||
    sourceRowId != null ||
    sourceRevision != null
  ) {
    throw new Error('店铺费用不关联订单；请先清除订单行绑定。')
  }
  return {
    label: text(raw.label, '费用名称', 100),
    category: raw.category,
    amount: money(raw.amount, '实际费用金额', true),
    currency,
    occurred_at: checkedInstant(raw.occurred_at, '发生时间', timezone),
    timezone,
    evidence_ref: text(raw.evidence_ref, '凭据编号', 120),
    evidence_note: text(raw.evidence_note, '事实依据', 1000),
    allocation: raw.allocation,
    order_line_id: raw.allocation === 'order_line' ? orderLineId : null,
    expected_source_row_id:
      raw.allocation === 'order_line' ? sourceRowId : null,
    expected_source_revision:
      raw.allocation === 'order_line' ? sourceRevision : null,
    reason: text(raw.reason, '本次录入或修订理由', 500),
  }
}
export function checkedExpenseScope(raw: ExpenseScope): ExpenseScope {
  if (!['user_import', 'synthetic'].includes(raw.data_identity))
    throw new Error('数据身份无效。')
  if (!channels.includes(raw.channel)) throw new Error('来源渠道无效。')
  const timezone = checkedTimezone(raw.timezone, '核对显示时区')
  const start = checkedInstant(raw.start_at, '开始时间', timezone, 2101)
  const end = checkedInstant(raw.end_at, '结束时间', timezone, 2101)
  const startYear = Number(start.slice(0, 4))
  const endYear = Number(end.slice(0, 4))
  if (startYear < 2000 || startYear > 2101 || endYear < 2000 || endYear > 2101)
    throw new Error('查询年份须在 2000—2101 之间。')
  const duration = Date.parse(end) - Date.parse(start)
  if (duration <= 0 || duration > 366 * 86400000)
    throw new Error('查询区间须大于零且不超过 366 天，包含开始、不含结束。')
  return {
    data_identity: raw.data_identity,
    channel: raw.channel,
    start_at: start,
    end_at: end,
    timezone,
  }
}
export function checkedFeeRuleContent(raw: FeeRuleContent): FeeRuleContent {
  if (!expenseCategoryKeys.includes(raw.category))
    throw new Error('统一费用类别无效。')
  return {
    fee_name: text(raw.fee_name, '完整原始收费名', 120),
    category: raw.category,
    reason: text(raw.reason, '本次规则依据与理由', 500),
  }
}
export function expenseActions(status: string): ControlAction[] {
  if (status === 'active' || status === 'stale') return ['withdraw', 'clear']
  if (status === 'withdrawn') return ['clear']
  return []
}
export function ruleActions(status: string): ControlAction[] {
  if (status === 'active') return ['withdraw', 'clear']
  if (status === 'withdrawn') return ['clear']
  return []
}
export function linkedOrder(
  order: ExpenseOrder | undefined,
  revision: number | null,
): {
  order_line_id: number
  expected_source_row_id: number
  expected_source_revision: number
} {
  if (!order || revision == null || !Number.isInteger(revision) || revision < 0)
    throw new Error('请先查找订单行并核对来源版本，再选择关联行。')
  return {
    order_line_id: order.id,
    expected_source_row_id: order.source.row_id,
    expected_source_revision: revision,
  }
}
