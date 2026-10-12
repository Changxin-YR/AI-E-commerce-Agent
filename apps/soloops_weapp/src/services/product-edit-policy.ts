import type { SourceChannel } from './import-types'
import type { DataIdentity } from './business-rule-policy'
import type { SourceReference } from './scope-types'
import type { QualityProduct } from './product-quality-policy'

export const editStatusLabels: Record<string, string> = {
  draft: '待审批草稿',
  applied: '本地已生效',
  failed: '整批未生效',
  rejected: '已拒绝',
  stale: '来源已失效',
  revoked: '已撤销',
  cleared: '正文已清除',
}
export const editItemResultLabels: Record<string, string> = {
  pending: '等待审批',
  applied: '本地修订已生效',
  conflict: '商品或来源已变化',
  blocked: '店铺数据版本已变化',
}
export const editControlLabels: Record<string, string> = {
  reject: '拒绝草稿',
  withdraw: '撤销本地修订',
  clear: '清除修订正文',
}
export const editMaxChanges = 50
export const editPageSize = 20
export type EditAction = 'approve' | 'reject' | 'withdraw' | 'clear'
export type EditControl = 'reject' | 'withdraw' | 'clear'

export interface EditProductValues {
  sku: string
  name: string
  facts: string
  price: string | null
  currency: string | null
  unit_cost: string | null
  cost_currency: string | null
}
export interface ProductChange {
  product_id: number
  expected_source_row_id: number
  name: string
  facts: string
}
export interface EditItem {
  product_id: number
  before: EditProductValues
  after: EditProductValues
  source: SourceReference
  result: 'pending' | 'applied' | 'conflict' | 'blocked'
  message: string
}
export interface EditSnapshot {
  source_revision: number
  data_identity: DataIdentity
  channel: SourceChannel
  reason: string
  items: EditItem[]
}
export interface EditSaved {
  id: number
  shop_id: number
  version: number
  status: string
  preview_hash: string
  snapshot: EditSnapshot | null
  output_batch_id: number | null
  created_at: string
  decided_at: string | null
  current_count: number
}
export interface EditPage {
  items: EditSaved[]
  next_cursor: number | null
}
export interface EditField {
  selected: boolean
  name: string
  facts: string
}
export interface EditCreateInput {
  data_identity: DataIdentity
  channel: SourceChannel
  reason: string
  changes: ProductChange[]
  request_id: string
}

export function catalogFields(
  products: QualityProduct[],
): Record<number, EditField> {
  return Object.fromEntries(
    products.map((product) => [
      product.product_id,
      { selected: false, name: product.name, facts: product.facts },
    ]),
  )
}
/** Only selected products whose name or facts actually differ become changes. */
export function changedProducts(
  products: QualityProduct[],
  fields: Record<number, EditField>,
): ProductChange[] {
  return products.flatMap((product) => {
    const field = fields[product.product_id]
    if (!field?.selected) return []
    if (field.name === product.name && field.facts === product.facts) return []
    return [
      {
        product_id: product.product_id,
        expected_source_row_id: product.source.row_id,
        name: field.name,
        facts: field.facts,
      },
    ]
  })
}
export function selectedCount(fields: Record<number, EditField>): number {
  return Object.values(fields).filter((field) => field.selected).length
}
export function checkedEditCreate(input: EditCreateInput): EditCreateInput {
  if (!['user_import', 'synthetic'].includes(input.data_identity))
    throw new Error('请选择有效的修订数据身份。')
  if (!input.channel) throw new Error('请选择来源渠道。')
  const reason = input.reason.trim()
  if (!reason) throw new Error('请填写修订依据。')
  if (reason.length > 500) throw new Error('修订依据最多 500 个字符。')
  if (!input.changes.length)
    throw new Error('请选择至少一个名称或参数有变化的商品。')
  if (input.changes.length > editMaxChanges)
    throw new Error(`每批最多 ${editMaxChanges} 个商品。`)
  const ids = new Set(input.changes.map((change) => change.product_id))
  if (ids.size !== input.changes.length)
    throw new Error('同一商品只能修订一次。')
  const changes = input.changes.map((change) => {
    const name = change.name.trim()
    if (!name) throw new Error('商品名称不能为空白。')
    if (name.length > 240) throw new Error('商品名称最多 240 个字符。')
    if (change.facts.length > 2000)
      throw new Error('商品参数最多 2000 个字符。')
    if (!Number.isInteger(change.product_id) || change.product_id < 1)
      throw new Error('商品编号无效，请重新加载商品。')
    if (
      !Number.isInteger(change.expected_source_row_id) ||
      change.expected_source_row_id < 1
    )
      throw new Error('商品来源行无效，请重新加载商品。')
    return {
      product_id: change.product_id,
      expected_source_row_id: change.expected_source_row_id,
      name,
      facts: change.facts,
    }
  })
  if (!input.request_id) throw new Error('缺少请求标识，请重新进入页面。')
  return {
    data_identity: input.data_identity,
    channel: input.channel,
    reason,
    changes,
    request_id: input.request_id,
  }
}
export function editGates(
  edit: Pick<EditSaved, 'status' | 'snapshot' | 'output_batch_id'>,
): Record<EditAction, boolean> {
  const draft = edit.status === 'draft' && !!edit.snapshot
  return {
    approve: draft,
    reject: draft,
    withdraw: !!edit.output_batch_id,
    clear: ['draft', 'applied', 'failed', 'stale'].includes(edit.status),
  }
}
export function approveGate(
  edit: Pick<EditSaved, 'status' | 'version' | 'preview_hash' | 'snapshot'>,
  confirmed: boolean,
): string[] {
  const reasons: string[] = []
  if (!confirmed) reasons.push('请先逐项核对差异与事实依据。')
  if (edit.status !== 'draft') reasons.push('仅待审批草稿可以批准。')
  if (!edit.snapshot?.items.length)
    reasons.push('草稿缺少差异明细，请重新加载。')
  if (!/^[a-f0-9]{64}$/.test(edit.preview_hash))
    reasons.push('差异指纹无效，请重新打开核对。')
  if (!Number.isInteger(edit.version) || edit.version < 1)
    reasons.push('修订版本无效，请重新加载。')
  return reasons
}
export function approvePayload(
  edit: Pick<EditSaved, 'status' | 'version' | 'preview_hash' | 'snapshot'>,
  confirmed: boolean,
): Record<string, unknown> {
  const reasons = approveGate(edit, confirmed)
  if (reasons.length) throw new Error(reasons.join(' '))
  return {
    version: edit.version,
    expected_preview_hash: edit.preview_hash,
    confirm: true,
  }
}
export function controlPayload(
  edit: Pick<EditSaved, 'status' | 'version' | 'output_batch_id'>,
  action: EditControl,
  confirmed: boolean,
): Record<string, unknown> {
  if (!confirmed) throw new Error('请先确认处理及其依赖影响。')
  if (!Number.isInteger(edit.version) || edit.version < 1)
    throw new Error('修订版本无效，请刷新后操作。')
  if (action === 'reject' && edit.status !== 'draft')
    throw new Error('仅待审草稿可以拒绝。')
  if (action === 'withdraw' && !edit.output_batch_id)
    throw new Error('该修订尚未本地生效，不能撤销。')
  if (action === 'clear' && edit.status === 'cleared')
    throw new Error('正文已清除，无需重复操作。')
  return { version: edit.version, confirm: true }
}
export function editItemDiff(item: EditItem): string {
  const nameChanged = item.before.name !== item.after.name ? '名称' : ''
  const factsChanged = item.before.facts !== item.after.facts ? '参数' : ''
  return [nameChanged, factsChanged].filter(Boolean).join(' / ') || '无变化'
}
export function editSummary(
  edit: Pick<EditSaved, 'status' | 'snapshot' | 'current_count'>,
): string {
  const items = edit.snapshot?.items.length ?? 0
  if (edit.status === 'applied')
    return `本批已执行 ${items} 项，当前 ${edit.current_count} 项仍为主档来源；后续导入或修订可能覆盖历史结果。`
  if (['failed', 'stale'].includes(edit.status))
    return '整批未生效；请重新加载当前商品，核对后建立新草稿。'
  return `本批 ${items} 项差异；金额沿用原来源，平台尚未同步。`
}
export function visibleProducts(
  products: QualityProduct[],
  page: number,
): QualityProduct[] {
  return products.slice(page * editPageSize, (page + 1) * editPageSize)
}
export function changedPreview(
  fields: Record<number, EditField>,
  prefix: string,
  appendFacts: string,
): boolean {
  return (
    Object.values(fields).some((field) => field.selected) &&
    (!!prefix.trim() || !!appendFacts.trim())
  )
}
export function unknownResult(cause: unknown): boolean {
  const error = cause as { status?: number; code?: string } | null
  return (
    !!error &&
    error.status === 0 &&
    error.code !== 'stale_response' &&
    error.code !== 'session_expired'
  )
}
