import type { SourceChannel } from './import-types'
import type { DataIdentity } from './business-rule-policy'
import type { SourceReference } from './scope-types'

export const qualityChannels: Record<string, string> = {
  generic: '通用 / 自建表',
  shopify: 'Shopify',
  amazon: 'Amazon',
  other: '其他来源',
}
export const qualityStatus: Record<string, string> = {
  current: '来源未变化',
  stale: '来源已变化，需重新检查',
  cleared: '正文已清除',
}
export const qualityIssueStatus: Record<string, string> = {
  missing: '缺少资料',
  review: '待人工复核',
}
export const qualityCoverageStatus: Record<string, string> = {
  checked: '已检查',
  not_checked: '未检查',
}
export const identityLabels: Record<string, string> = {
  user_import: '用户导入文件',
  synthetic: '合成测试数据',
}

export interface QualityScope {
  data_identity: DataIdentity
  channel: SourceChannel | null
  sku_prefix: string
}
export interface QualityIssue {
  code: string
  field: string
  status: 'missing' | 'review'
  reason: string
  suggestion: string
}
export interface QualityProduct {
  product_id: number
  sku: string
  name: string
  facts: string
  price: string | null
  currency: string | null
  unit_cost: string | null
  cost_currency: string | null
  channel: string
  source: SourceReference
  issues: QualityIssue[]
  similar_skus: string[]
  similar_sku_count: number
}
export interface QualityCoverage {
  code: string
  label: string
  status: 'checked' | 'not_checked'
  reason: string
}
export interface QualityResult {
  shop_id: number
  scope: QualityScope
  source_revision: number
  checked_at: string
  rule_version: string
  preview_hash: string
  product_count: number
  affected_products: number
  missing_count: number
  review_count: number
  coverage: QualityCoverage[]
  limitations: string[]
  products: QualityProduct[]
}
export interface QualitySaved {
  id: number
  shop_id: number
  status: 'current' | 'stale' | 'cleared'
  created_at: string
  scope: QualityScope
  snapshot: QualityResult | null
}
export interface QualityPage {
  items: QualitySaved[]
  next_cursor: number | null
}
export interface QualityForm {
  data_identity: DataIdentity
  channel: string
  sku_prefix: string
}

export function defaultQualityForm(): QualityForm {
  return { data_identity: 'user_import', channel: '', sku_prefix: '' }
}
export function qualityForm(scope: QualityScope): QualityForm {
  return {
    data_identity: scope.data_identity,
    channel: scope.channel ?? '',
    sku_prefix: scope.sku_prefix,
  }
}
export function checkedQualityScope(form: QualityForm): QualityScope {
  if (!['user_import', 'synthetic'].includes(form.data_identity))
    throw new Error('请选择有效的检查数据身份。')
  if (form.channel && !qualityChannels[form.channel])
    throw new Error('请选择有效的来源渠道。')
  const prefix = form.sku_prefix.trim()
  if (prefix.length > 120) throw new Error('SKU 前缀最多 120 个字符。')
  return {
    data_identity: form.data_identity,
    channel: (form.channel || null) as SourceChannel | null,
    sku_prefix: prefix,
  }
}
export function dirtyQualityForm(
  form: QualityForm,
  scope: QualityScope | undefined,
): boolean {
  return !!scope && JSON.stringify(form) !== JSON.stringify(qualityForm(scope))
}
/** Saving re-checks the exact preview the seller reviewed; a changed hash must fail. */
export function qualitySavePayload(
  result: Pick<QualityResult, 'scope' | 'source_revision' | 'preview_hash'>,
  requestId: string,
  confirmed: boolean,
): Record<string, unknown> {
  if (!confirmed) throw new Error('请先查看范围与未检查项并确认保存。')
  if (!/^[a-f0-9]{64}$/.test(result.preview_hash))
    throw new Error('预览指纹无效，请重新检查后再保存。')
  if (!Number.isInteger(result.source_revision) || result.source_revision < 0)
    throw new Error('来源版本无效，请重新检查后再保存。')
  if (!requestId) throw new Error('缺少请求标识，请重新进入页面。')
  return {
    scope: result.scope,
    expected_revision: result.source_revision,
    expected_preview_hash: result.preview_hash,
    request_id: requestId,
    confirm: true,
  }
}
export function clearsQualityReport(
  saved: Pick<QualitySaved, 'status'> | undefined,
): boolean {
  return !!saved && saved.status !== 'cleared'
}
export function coverageGaps(
  result: Pick<QualityResult, 'coverage'>,
): QualityCoverage[] {
  return result.coverage.filter((item) => item.status === 'not_checked')
}
export function qualitySummary(result: QualityResult): string {
  return `共 ${result.product_count} 个商品 · 有缺项或待复核 ${result.affected_products} 个 · 缺失 ${result.missing_count} 项 · 待复核 ${result.review_count} 项 · 规则 ${result.rule_version}`
}
export function productMoney(
  amount: string | null,
  currency: string | null,
): string {
  if (amount == null || amount === '') return '未知'
  return currency ? `${amount} ${currency}` : amount
}
export function productIssues(product: QualityProduct): string[] {
  return product.issues.map(
    (issue) =>
      `${qualityIssueStatus[issue.status] ?? issue.status} · ${issue.field}：${issue.reason}（建议：${issue.suggestion}）`,
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
