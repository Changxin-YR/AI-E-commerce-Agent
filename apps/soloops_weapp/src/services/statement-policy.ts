// H13 渠道账单（web_route: /statements）与 H14 订单账单核对
// （web_route: /order-reconciliation）共用的纯逻辑。
// 只放可离线测试的校验/派生逻辑，不放请求，不依赖 Taro 或会话。
import type { SourceReference } from './scope-types'

export type DataIdentity = 'user_import' | 'synthetic'
export type SourceChannel = 'generic' | 'shopify' | 'amazon' | 'other'
export type EntryType = 'sale' | 'refund' | 'fee' | 'payout'
export type ControlAction = 'withdraw' | 'clear'
export type RecordStatus = 'active' | 'stale' | 'withdrawn' | 'cleared'
export type ReviewOutcome = 'consistent' | 'differences_recorded' | 'pending'
export type SaleBasis = 'unknown' | 'merchandise_after_discount'

export interface StatementScope {
  data_identity: DataIdentity
  channel: SourceChannel
  start_at: string
  end_at: string
  timezone: string
}

export interface OrderReconciliationScope extends StatementScope {
  sale_basis: SaleBasis
  basis_note: string
}

export interface StatementItem {
  id: number
  statement_id: string
  line_id: string
  entry_type: EntryType
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

export interface StatementTotal {
  currency: string
  entry_type: string
  amount: string
  count: number
}

export interface MatchedExpense {
  id: number
  version: number
  label: string
  category: string
  allocation: string
  evidence_ref: string
  amount: string
  currency: string
  occurred_at: string
}

export type FeeComparisonStatus =
  | 'matched'
  | 'amount_difference'
  | 'statement_only'
  | 'expense_only'
  | 'ambiguous'
  | 'currency_mismatch'

export interface FeeComparison {
  evidence_ref: string
  status: FeeComparisonStatus
  statement_ids: number[]
  expenses: MatchedExpense[]
  difference: string | null
}

export type MappingStatus =
  | 'mapped'
  | 'unmapped'
  | 'ambiguous'
  | 'currency_mismatch'
  | 'category_conflict'

export interface FeeMapping {
  statement_id: number
  status: MappingStatus
  category: string | null
  rule_id: number | null
  rule_version: number | null
}

export interface StatementReconciliation {
  scope: StatementScope
  source_revision: number
  rule_revision: number
  calculated_at: string
  statements: StatementItem[]
  totals: StatementTotal[]
  comparisons: FeeComparison[]
  mappings: FeeMapping[]
  stale_expenses: number
  withdrawn_expenses: number
  checks: string[]
}

export interface ReviewConclusion {
  outcome: ReviewOutcome
  note: string
}

export interface ReviewSnapshot {
  conclusion: ReviewConclusion
  result: StatementReconciliation
  expense_revision: number
  blockers: string[]
}

export interface ReviewPreview {
  preview_hash: string
  snapshot: ReviewSnapshot
}

export interface ReviewHistoryEntry {
  version: number
  action: string
  conclusion: ReviewConclusion | null
  created_at: string
}

export interface ReviewSaved {
  id: number
  shop_id: number
  data_identity: DataIdentity
  channel: SourceChannel
  status: RecordStatus
  version: number
  content_version: number
  created_at: string
  snapshot: ReviewSnapshot | null
  history: ReviewHistoryEntry[]
}

export interface ReviewPage {
  items: ReviewSaved[]
  next_cursor: number | null
}

export interface ReviewCurrent {
  record: ReviewSaved
  preview: ReviewPreview | null
}

export interface ReviewDraftBody {
  scope: StatementScope
  review_id: number | null
  version: number
  conclusion: ReviewConclusion
}

export interface ReviewWriteBody extends ReviewDraftBody {
  preview_hash: string
  request_id: string
  confirm: true
}

export interface ReviewControlBody {
  request_id: string
  version: number
  confirm: true
}

export interface ReconciliationOrder {
  id: number
  order_id: string
  line_id: string
  sku: string
  quantity: number
  unit_price: string
  currency: string
  ordered_at: string
  status: string
  discount: string | null
  refund: string | null
  fulfillment_status: string
  in_window: boolean
  source: SourceReference
}

export interface ReconciliationStatement extends StatementItem {
  in_window: boolean
}

export interface OrderComparison {
  order_id: string
  entry_type: 'sale' | 'refund'
  statement_ids: number[]
  order_line_ids: number[]
  status: 'matched' | 'amount_difference' | 'pending'
  reasons: string[]
  currency: string | null
  order_amount: string | null
  difference: string | null
}

export interface OrderReconciliation {
  scope: OrderReconciliationScope
  source_revision: number
  calculated_at: string
  coverage: 'unknown'
  orders: ReconciliationOrder[]
  statements: ReconciliationStatement[]
  comparisons: OrderComparison[]
  checks: string[]
}

export const identities: DataIdentity[] = ['user_import', 'synthetic']
export const channels: SourceChannel[] = [
  'generic',
  'shopify',
  'amazon',
  'other',
]
export const reviewOutcomes: Record<ReviewOutcome, string> = {
  consistent: '核对一致',
  differences_recorded: '金额差异已说明',
  pending: '保持待核',
}
export const reviewOutcomeKeys = Object.keys(reviewOutcomes) as ReviewOutcome[]
export const reviewStatuses: Record<string, string> = {
  active: '有效 · 保存时依据一致',
  stale: '来源或费用变化 · 待重核',
  withdrawn: '已撤销 · 保留历史',
  cleared: '正文已清除',
}
export const entryTypes: Record<string, string> = {
  sale: '销售款',
  refund: '退款',
  fee: '费用',
  payout: '平台记载回款',
}
export const comparisonStatuses: Record<FeeComparisonStatus, string> = {
  matched: '编号币种金额一致 · 类别仍待人工核对',
  amount_difference: '金额差异 · 待核',
  statement_only: '仅账单一方 · 待核',
  expense_only: '仅人工费用一方 · 待核',
  ambiguous: '重复凭据 · 整组待核',
  currency_mismatch: '币种不一致 · 不换汇',
}
export const mappingStatuses: Record<MappingStatus, string> = {
  mapped: '已按规则分类 · 业务待核',
  unmapped: '未匹配收费规则 · 待核',
  ambiguous: '重复凭据或规则 · 待核',
  currency_mismatch: '币种不一致 · 待核',
  category_conflict: '与人工费用类别冲突 · 待核',
}
export const orderComparisonStatuses: Record<string, string> = {
  matched: '可比口径金额一致 · 其他依据仍待核',
  amount_difference: '金额差异 · 待核',
  pending: '待核 · 缺少可比条件',
}
export const saleBasisLabels: Record<SaleBasis, string> = {
  unknown: '尚未核实金额组成，仅查看待核依据',
  merchandise_after_discount: '已核实两侧均为退款前折后商品款',
}
export const controls: Record<ControlAction, string> = {
  withdraw: '撤销 · 保留历史并排除出当前结论',
  clear: '清除 · 擦除全部历史正文与依据',
}
export const statementLinesPerPage = 20
export const reviewsPerPage = 20
export const ordersPerPage = 20
export const statementsPerPage = 20

const INSTANT =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d{1,9})?(Z|[+-]\d{2}:\d{2})$/

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
  // match[7] 是显式偏移（Z 或 ±HH:MM）。
  const offset = explicitOffset(match[7] ?? '')
  if (
    offset !== null &&
    offset !== zoneOffsetMinutes(new Date(parsed), timezone)
  )
    throw new Error(`${label}的偏移与所选 IANA 时区不符，请按该时区重新填写。`)
  return instant
}
export function checkedScope(raw: StatementScope): StatementScope {
  if (!identities.includes(raw.data_identity)) throw new Error('数据身份无效。')
  if (!channels.includes(raw.channel)) throw new Error('来源渠道无效。')
  const timezone = checkedTimezone(raw.timezone, '核对显示时区')
  const start = checkedInstant(raw.start_at, '开始时间', timezone)
  const end = checkedInstant(raw.end_at, '结束时间', timezone)
  const duration = Date.parse(end) - Date.parse(start)
  if (duration <= 0 || duration > 366 * 86400000)
    throw new Error('核对区间须大于零且不超过 366 天，包含开始、不含结束。')
  return {
    data_identity: raw.data_identity,
    channel: raw.channel,
    start_at: start,
    end_at: end,
    timezone,
  }
}
export function checkedOrderScope(
  raw: OrderReconciliationScope,
): OrderReconciliationScope {
  const scope = checkedScope(raw)
  if (
    raw.sale_basis !== 'unknown' &&
    raw.sale_basis !== 'merchandise_after_discount'
  )
    throw new Error('销售金额口径无效。')
  const note = raw.basis_note.trim()
  if (raw.sale_basis !== 'unknown' && !note)
    throw new Error('选择可比销售口径时须填写两侧原文件的金额组成依据。')
  if (note.length > 500) throw new Error('金额组成依据不能超过 500 个字符。')
  return { ...scope, sale_basis: raw.sale_basis, basis_note: note }
}
export function checkedReviewConclusion(
  raw: ReviewConclusion,
): ReviewConclusion {
  if (!reviewOutcomeKeys.includes(raw.outcome))
    throw new Error('人工结论无效。')
  return {
    outcome: raw.outcome,
    note: text(raw.note, '核对依据与差异说明', 1000),
  }
}
export function checkedReviewDraft(raw: ReviewDraftBody): ReviewDraftBody {
  const reviewId = raw.review_id
  if (reviewId !== null) {
    if (!Number.isInteger(reviewId) || reviewId <= 0)
      throw new Error('核对存档编号无效，请重新读取记录。')
  }
  if (!Number.isInteger(raw.version) || raw.version < 0)
    throw new Error('核对存档版本无效，请重新读取记录。')
  if (reviewId === null && raw.version !== 0)
    throw new Error('新建存档版本必须为零，请重新开始。')
  return {
    scope: checkedScope(raw.scope),
    review_id: reviewId,
    version: raw.version,
    conclusion: checkedReviewConclusion(raw.conclusion),
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
): ReviewControlBody {
  if (!Number.isInteger(version) || version < 1)
    throw new Error('核对存档版本无效，请重新读取记录。')
  return { request_id: request, version, confirm: true }
}
// 服务端在有待核事项（blockers）或金额差异时只接受对应结论；页面按 blockers 提示。
export function blockedOutcomes(blockers: string[]): ReviewOutcome[] {
  if (!blockers.length) return []
  return ['consistent', 'differences_recorded']
}
export function isCurrentVersion(
  saved: Pick<ReviewSaved, 'content_version'>,
  shown: number | null,
): boolean {
  return shown === saved.content_version
}
export function canEdit(saved: ReviewSaved): boolean {
  return (
    (saved.status === 'active' || saved.status === 'stale') &&
    saved.snapshot !== null
  )
}
export function emptyStatementScope(
  timezone = 'Asia/Shanghai',
  now: Date = new Date(),
): StatementScope {
  const start = new Date(now.getTime() - 30 * 86400000)
  return {
    data_identity: 'user_import',
    channel: 'generic',
    start_at: localIso(start, timezone),
    end_at: localIso(now, timezone),
    timezone,
  }
}
export function emptyOrderScope(
  timezone = 'Asia/Shanghai',
  now: Date = new Date(),
): OrderReconciliationScope {
  return {
    ...emptyStatementScope(timezone, now),
    sale_basis: 'unknown',
    basis_note: '',
  }
}
export function emptyConclusion(): ReviewConclusion {
  return { outcome: 'pending', note: '' }
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
export function statementLineLabel(line: StatementItem, index: number): string {
  const parts = [
    `${index + 1}. ${entryTypes[line.entry_type] || line.entry_type}`,
  ]
  parts.push(`账单 ${line.statement_id} / 行 ${line.line_id}`)
  if (line.fee_name) parts.push(line.fee_name)
  if (line.order_id) parts.push(`订单 ${line.order_id}`)
  if (line.evidence_ref) parts.push(`凭据 ${line.evidence_ref}`)
  return parts.join(' · ')
}
// 契约动作 ID 常量：便于与 contracts/ui-contract.json 逐条对照。
export const statementActionIds = {
  reconcile: 'reconcile_api_shops__shop_id__statements_reconcile_post',
  preview: 'preview_api_shops__shop_id__statement_reviews_preview_post',
  write: 'write_api_shops__shop_id__statement_reviews_post',
  page: 'page_api_shops__shop_id__statement_reviews_get',
  get: 'get_api_shops__shop_id__statement_reviews__review_id__get',
  current:
    'read_current_api_shops__shop_id__statement_reviews__review_id__current_get',
  control:
    'control_api_shops__shop_id__statement_reviews__review_id___action__post',
} as const
export const statementRouteQueries = {
  reconcile: 'POST /shops/{shop_id}/statements/reconcile',
  preview: 'POST /shops/{shop_id}/statement-reviews/preview',
  write: 'POST /shops/{shop_id}/statement-reviews',
  page: 'GET /shops/{shop_id}/statement-reviews',
  get: 'GET /shops/{shop_id}/statement-reviews/{review_id}',
  current: 'GET /shops/{shop_id}/statement-reviews/{review_id}/current',
  control: 'POST /shops/{shop_id}/statement-reviews/{review_id}/{action}',
} as const
export const orderActionIds = {
  reconcileOrders:
    'reconcile_orders_api_shops__shop_id__statements_orders_reconcile_post',
} as const
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
export const orderRouteQueries = {
  reconcileOrders: 'POST /shops/{shop_id}/statements/orders/reconcile',
} as const
