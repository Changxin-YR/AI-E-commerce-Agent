import type { SourceChannel } from './import-types'

export type DataIdentity = 'user_import' | 'synthetic'
export type RuleAction = 'save' | 'revoke' | 'reset' | 'restore'
export const channels: SourceChannel[] = [
  'generic',
  'shopify',
  'amazon',
  'other',
]
export const identities: DataIdentity[] = ['user_import', 'synthetic']
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
// Mirrors CreateAuthorization: max_uses 1–20, valid_hours 1–168.
export const authorizationMaxUses = 20
export const authorizationMaxHours = 168

export interface RuleNotes {
  target_site: string
  warehouse: string
  logistics: string
  brand_voice: string
  support_wording: string
}
export interface RuleValues {
  max_age_hours: number
  min_quantity: number
  max_margin_percent: string
  advertising_daily_budget: string | null
  currency: string
  notes: RuleNotes
  basis: string
  automation: 'manual_only'
}
export interface RuleRevision {
  version: number
  previous_version: number
  restored_from: number | null
  shop_id: number
  channel: string
  data_identity: string
  action: string
  active: boolean
  values: RuleValues
  created_at: string | null
}
export interface RuleChange {
  channel: SourceChannel
  data_identity: DataIdentity
  expected_version: number
  action: RuleAction
  values?: RuleValues
  restore_version?: number
}
/** Editable text form; money and percentages stay decimal strings. */
export interface RuleForm {
  max_age_hours: string
  min_quantity: string
  max_margin_percent: string
  advertising_daily_budget: string
  currency: string
  notes: RuleNotes
  basis: string
}
export interface RuleChangeInput {
  channel: SourceChannel
  data_identity: DataIdentity
  expected_version: number
  action: RuleAction
  form?: RuleForm
  restore_version?: number | null
}
export const noteLabels: {
  key: keyof RuleNotes
  label: string
  max: number
}[] = [
  { key: 'target_site', label: '目标站点', max: 200 },
  { key: 'warehouse', label: '常用仓库', max: 200 },
  { key: 'logistics', label: '物流偏好', max: 500 },
  { key: 'brand_voice', label: '品牌语言规范', max: 1000 },
  { key: 'support_wording', label: '客服话术偏好', max: 1000 },
]
export const ruleActionLabels: Record<string, string> = {
  save: '保存',
  restore: '恢复历史',
  revoke: '撤销',
  reset: '重置',
  default: '初始口径',
}
export const authorizationLabels: Record<string, string> = {
  active: '有效',
  revoked: '已撤销',
  expired: '已到期',
  exhausted: '次数已用尽',
  source_changed: '来源已变化或过期',
  rules_changed: '经营规则已变化',
}

export function emptyRuleNotes(): RuleNotes {
  return {
    target_site: '',
    warehouse: '',
    logistics: '',
    brand_voice: '',
    support_wording: '',
  }
}
export function defaultRuleValues(): RuleValues {
  return {
    max_age_hours: 24,
    min_quantity: 1,
    max_margin_percent: '20',
    advertising_daily_budget: null,
    currency: 'USD',
    notes: emptyRuleNotes(),
    basis: '系统初始检查口径',
    automation: 'manual_only',
  }
}
export function ruleForm(values: RuleValues): RuleForm {
  return {
    max_age_hours: String(values.max_age_hours),
    min_quantity: String(values.min_quantity),
    max_margin_percent: values.max_margin_percent,
    advertising_daily_budget: values.advertising_daily_budget ?? '',
    currency: values.currency,
    notes: { ...emptyRuleNotes(), ...values.notes },
    basis: values.basis,
  }
}
export function checkedRuleChange(input: RuleChangeInput): RuleChange {
  if (!channels.includes(input.channel))
    throw new Error('请选择有效的规则渠道。')
  if (!identities.includes(input.data_identity))
    throw new Error('请选择有效的规则数据身份。')
  if (!Number.isInteger(input.expected_version) || input.expected_version < 0)
    throw new Error('当前规则版本无效，请重新读取。')
  if (!['save', 'revoke', 'reset', 'restore'].includes(input.action))
    throw new Error('不支持的规则操作。')
  const base = {
    channel: input.channel,
    data_identity: input.data_identity,
    expected_version: input.expected_version,
  }
  if (input.action === 'restore') {
    const version = Number(input.restore_version)
    if (!Number.isInteger(version) || version < 1)
      throw new Error('请选择要恢复的历史版本。')
    return { ...base, action: 'restore', restore_version: version }
  }
  if (input.action !== 'save') return { ...base, action: input.action }
  if (!input.form) throw new Error('请先填写完整规则再保存。')
  return { ...base, action: 'save', values: checkedRuleValues(input.form) }
}
export function checkedRuleValues(form: RuleForm): RuleValues {
  const maxAge = whole(form.max_age_hours, 1, 720, '库存有效小时')
  const quantity = whole(form.min_quantity, 1, 1_000_000, '低毛利最少销量')
  const margin = decimal(form.max_margin_percent, -1000, 100, 2, '低毛利阈值')
  const budget =
    form.advertising_daily_budget.trim() === ''
      ? null
      : decimal(
          form.advertising_daily_budget,
          0,
          100_000_000,
          4,
          '每日广告计划金额',
        )
  const notes = { ...emptyRuleNotes(), ...form.notes }
  for (const item of noteLabels) {
    const text = String(notes[item.key] ?? '')
    if (text.length > item.max)
      throw new Error(`${item.label}最多 ${item.max} 个字符。`)
    notes[item.key] = text
  }
  const basis = form.basis.trim()
  if (!basis) throw new Error('请填写规则依据。')
  if (basis.length > 500) throw new Error('规则依据最多 500 个字符。')
  const currency = form.currency.trim()
  if (!currency) throw new Error('请选择预算币种。')
  return {
    max_age_hours: maxAge,
    min_quantity: quantity,
    max_margin_percent: margin,
    advertising_daily_budget: budget,
    currency,
    notes,
    basis,
    automation: 'manual_only',
  }
}
/** Save is always available; other actions only make sense on an active revision. */
export function ruleActionGates(
  revision: Pick<RuleRevision, 'active' | 'version'>,
): Record<RuleAction, boolean> {
  const active = revision.active && revision.version > 0
  return { save: true, revoke: active, reset: true, restore: active }
}
export function dirtyRuleForm(form: RuleForm, values: RuleValues): boolean {
  return JSON.stringify(form) !== JSON.stringify(ruleForm(values))
}
function whole(value: string, min: number, max: number, label: string): number {
  const text = value.trim(),
    number = Number(text)
  if (!/^\d+$/.test(text) || !Number.isInteger(number))
    throw new Error(`${label}须为整数。`)
  if (number < min || number > max)
    throw new Error(`${label}须在 ${min}–${max} 之间。`)
  return number
}
function decimal(
  value: string,
  min: number,
  max: number,
  places: number,
  label: string,
): string {
  const text = value.trim()
  if (!/^-?\d+(?:\.\d+)?$/.test(text))
    throw new Error(`${label}须为十进制数字。`)
  const fraction = text.split('.')[1] ?? ''
  if (fraction.length > places)
    throw new Error(`${label}最多保留 ${places} 位小数。`)
  const number = Number(text)
  if (!Number.isFinite(number) || number < min || number > max)
    throw new Error(`${label}须在 ${min}–${max} 之间。`)
  return text
}
/** Network failures keep the request id; context switches are not business unknowns. */
export function unknownResult(cause: unknown): boolean {
  const error = cause as { status?: number; code?: string } | null
  return (
    !!error &&
    error.status === 0 &&
    error.code !== 'stale_response' &&
    error.code !== 'session_expired'
  )
}

export interface GrantScope {
  start_at: string
  end_at: string
  timezone: string
  currency: string
  channel: string
  data_identity: string
  rule_revision_id: number
  max_age_hours: number
  min_quantity: number
  max_margin_percent: string
}
export interface AuthorizationUse {
  id: number
  execution_id: number
  operation_run_id: number
  changes: { task_id: number; before: string; after: string; version: number }[]
  reused_count: number
  created_at: string
  reverted_at: string | null
}
export interface AuthorizationGrant {
  id: number
  shop_id: number
  version: number
  origin_execution_id: number
  scope: GrantScope
  risk: string
  skill: string
  source_revision: number
  candidate_count: number
  max_uses: number
  used_count: number
  status: string
  expires_at: string
  source_valid_until: string | null
  revoked_at: string | null
  created_at: string
  uses: AuthorizationUse[]
}
export interface AuthorizationPage {
  items: AuthorizationGrant[]
  next_before_id: number | null
}
/** The run the client must re-read before a bounded authorization can be created. */
export interface RunFacts {
  id: number
  shop_id: number
  version: number
  template: string
  status: string
  next_node: string | null
  source_status: string
  source_revision: number
  input: { scope: GrantScope } | null
}
export interface AuthorizationForm {
  execution_id: string
  max_uses: string
  valid_hours: string
}
export function authorizationGate(run: RunFacts | undefined): string[] {
  if (!run) return ['请先读取并核对要授权的任务。']
  const reasons: string[] = []
  if (run.template !== 'daily') reasons.push('仅日常巡检任务可创建预授权。')
  if (run.status !== 'waiting_approval')
    reasons.push('任务当前不在待审批状态。')
  if (run.next_node !== 'propose_tasks')
    reasons.push('任务当前节点不是候选审批。')
  if (run.source_status !== 'current')
    reasons.push('任务来源已变化，需重新检查。')
  if (!run.input?.scope) reasons.push('任务缺少已审范围。')
  return reasons
}
export function checkedAuthorization(
  form: AuthorizationForm,
  requestId: string,
  run: RunFacts | undefined,
): Record<string, unknown> {
  // The page never trusts free-form numbers for a server-side precondition.
  const reasons = authorizationGate(run)
  if (reasons.length) throw new Error(reasons.join(' '))
  if (String(run?.id) !== form.execution_id.trim())
    throw new Error('执行编号已变化，请重新核对任务。')
  const maxUses = whole(form.max_uses, 1, authorizationMaxUses, '最大次数')
  const hours = whole(form.valid_hours, 1, authorizationMaxHours, '有效小时')
  if (!requestId) throw new Error('缺少请求标识，请重新进入页面。')
  return {
    request_id: requestId,
    execution_id: run?.id,
    expected_version: run?.version,
    max_uses: maxUses,
    valid_hours: hours,
    confirmed: true,
  }
}
export function canRevokeGrant(
  grant: Pick<AuthorizationGrant, 'status'>,
): boolean {
  return grant.status === 'active'
}
export function revertableUses(
  grant: Pick<AuthorizationGrant, 'uses'>,
): AuthorizationUse[] {
  return grant.uses.filter((use) => !use.reverted_at && use.changes.length > 0)
}
export function grantScopeText(scope: GrantScope): string {
  return `${scope.start_at} → ${scope.end_at} · ${scope.timezone} · ${scope.currency} · ${scope.channel} / ${scope.data_identity} · 规则 #${scope.rule_revision_id} · 库存 ${scope.max_age_hours}h · 销量 ≥${scope.min_quantity} · 毛利 ≤${scope.max_margin_percent}%`
}
