import type { SourceChannel } from './import-types'
import type { DataIdentity } from './business-rule-policy'
import { currencies } from './business-rule-policy.ts'

export type ScheduleTask = 'operations' | 'report'
export type ScheduleFrequency = 'daily' | 'weekly' | 'monthly'
export type ScheduleAction = 'pause' | 'resume' | 'revoke' | 'edit'
export const scheduleMaxPlans = 100
export const scheduleFrequencies: ScheduleFrequency[] = [
  'daily',
  'weekly',
  'monthly',
]
export const channels: SourceChannel[] = [
  'generic',
  'shopify',
  'amazon',
  'other',
]
export const identities: DataIdentity[] = ['user_import', 'synthetic']
export const currencyCodes = currencies

export interface ScheduleConfig {
  name: string
  task: ScheduleTask
  report_currencies: string[]
  timezone: string
  frequency: ScheduleFrequency
  local_time: string
  weekday: number
  month_day: number
  lookback_days: number
  channel: SourceChannel
  data_identity: DataIdentity
  currency: string
  rule_revision_id: number
  max_age_hours: number
  min_quantity: number
  max_margin_percent: string
  quiet_start: number | null
  quiet_end: number | null
}
export interface ScheduleRow {
  id: number
  shop_id: number
  status: string
  version: number
  config: ScheduleConfig
  next_run_at: string | null
  created_at: string
}
export interface Occurrence {
  id: number
  shop_id: number
  schedule_id: number
  schedule_version: number
  trigger: string
  scheduled_at: string
  coalesced_from: string | null
  execution_id: number | null
  task: ScheduleTask
  report_id: number | null
  status: string
  reason: string
  notify_at: string
  read_at: string | null
  created_at: string
}
export interface ScheduleStatus {
  worker_enabled: boolean
  latest_timer: Occurrence | null
}
export interface ScheduleForm {
  name: string
  task: ScheduleTask
  report_currencies: string[]
  timezone: string
  frequency: ScheduleFrequency
  local_time: string
  weekday: string
  month_day: string
  lookback_days: string
  channel: SourceChannel
  data_identity: DataIdentity
  currency: string
  rule_revision_id: number
  max_age_hours: string
  min_quantity: string
  max_margin_percent: string
  quiet: boolean
  quiet_start: string
  quiet_end: string
}
export const scheduleLabels: Record<string, string> = {
  active: '已启用',
  paused: '已暂停',
  revoked: '已撤销',
  waiting_approval: '等待审批',
  succeeded: '检查完成',
  blocked: '检查受阻',
  missed: '错过周期',
  ready: '等待继续',
  circuit_open: '读取失败',
  cancelled: '已取消',
}
export const frequencyLabels: Record<string, string> = {
  daily: '每天',
  weekly: '每周',
  monthly: '每月',
}
export const weekdayLabels = [
  '周一',
  '周二',
  '周三',
  '周四',
  '周五',
  '周六',
  '周日',
]
export const occurrenceReasons: Record<string, string> = {
  conflict: '经营规则发生变化，请修改计划并核对当前规则。',
  local_check_failed: '本次运行未完成，已回滚；核对后可恢复计划。',
  range_too_large: '数据量超过本次检查上限，请缩小范围。',
  too_many_findings: '候选数量超过本次检查上限，请缩小范围。',
  invalid_local_date: '报告日期起点在所选时区不存在，请核对运行时区和日期。',
  report_saved: '经营报表已保存，可从运行历史查看报表与依据。',
  outside_recovery_window: '最近一期已超过 24 小时补跑窗口，等待下一周期。',
}

export function defaultScheduleForm(
  timezone: string,
  currency: string,
): ScheduleForm {
  return {
    name: '每日运营检查',
    task: 'operations',
    report_currencies: [],
    timezone,
    frequency: 'daily',
    local_time: '09:00',
    weekday: '0',
    month_day: '1',
    lookback_days: '7',
    channel: 'generic',
    data_identity: 'user_import',
    currency,
    rule_revision_id: 0,
    max_age_hours: '24',
    min_quantity: '1',
    max_margin_percent: '20',
    quiet: false,
    quiet_start: '22',
    quiet_end: '8',
  }
}
export function scheduleForm(config: ScheduleConfig): ScheduleForm {
  return {
    name: config.name,
    task: config.task,
    report_currencies: [...config.report_currencies],
    timezone: config.timezone,
    frequency: config.frequency,
    local_time: config.local_time,
    weekday: String(config.weekday),
    month_day: String(config.month_day),
    lookback_days: String(config.lookback_days),
    channel: config.channel,
    data_identity: config.data_identity,
    currency: config.currency,
    rule_revision_id: config.rule_revision_id,
    max_age_hours: String(config.max_age_hours),
    min_quantity: String(config.min_quantity),
    max_margin_percent: config.max_margin_percent,
    quiet: config.quiet_start !== null && config.quiet_end !== null,
    quiet_start: String(config.quiet_start ?? 22),
    quiet_end: String(config.quiet_end ?? 8),
  }
}
export function checkedScheduleConfig(form: ScheduleForm): ScheduleConfig {
  const name = form.name.trim()
  if (!name) throw new Error('请填写计划名称。')
  if (name.length > 80) throw new Error('计划名称最多 80 个字符。')
  if (!['operations', 'report'].includes(form.task))
    throw new Error('请选择计划内容。')
  if (!scheduleFrequencies.includes(form.frequency))
    throw new Error('请选择执行周期。')
  const timezone = form.timezone.trim()
  if (!timezone) throw new Error('请填写运行时区。')
  try {
    new Intl.DateTimeFormat('en', { timeZone: timezone })
  } catch {
    throw new Error('运行时区不是有效的 IANA 时区。')
  }
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(form.local_time))
    throw new Error('当地运行时间须为 HH:MM（00:00–23:59）。')
  if (!channels.includes(form.channel))
    throw new Error('请选择有效的检查渠道。')
  if (!identities.includes(form.data_identity))
    throw new Error('请选择有效的检查数据身份。')
  let weekday = whole(form.weekday, 0, 6, '星期')
  const monthDay = whole(form.month_day, 1, 28, '每月日期')
  const lookback = whole(form.lookback_days, 1, 365, '订单回看天数')
  const maxAge = whole(form.max_age_hours, 1, 720, '库存有效小时')
  const quantity = whole(form.min_quantity, 1, 1_000_000, '低毛利最少销量')
  const margin = decimal(form.max_margin_percent, -1000, 100, 2, '低毛利阈值')
  const ruleRevision = whole(
    String(form.rule_revision_id),
    0,
    1_000_000_000,
    '经营规则版本',
  )
  let quietStart: number | null = null,
    quietEnd: number | null = null
  if (form.quiet) {
    quietStart = whole(form.quiet_start, 0, 23, '免打扰开始小时')
    quietEnd = whole(form.quiet_end, 0, 23, '免打扰结束小时')
    if (quietStart === quietEnd) throw new Error('免打扰起止小时不能相同。')
  }
  const channel =
    form.task === 'report' ? ('generic' as SourceChannel) : form.channel
  const reportCurrencies = [
    ...new Set(form.report_currencies.map((c) => c.trim())),
  ]
    .filter(Boolean)
    .sort()
  if (reportCurrencies.length > 9) throw new Error('报表币种最多选择 9 个。')
  const currency = form.currency.trim()
  if (!currency) throw new Error('请选择统计币种。')
  if (form.task === 'report') {
    // 经营周报每周一、月报每月 1 日生成，且使用独立阈值覆盖全部渠道。
    weekday = 0
    return {
      name,
      task: 'report',
      report_currencies: reportCurrencies,
      timezone,
      frequency: form.frequency,
      local_time: form.local_time,
      weekday: 0,
      month_day: 1,
      lookback_days: lookback,
      channel: 'generic',
      data_identity: form.data_identity,
      currency,
      rule_revision_id: 0,
      max_age_hours: maxAge,
      min_quantity: quantity,
      max_margin_percent: margin,
      quiet_start: quietStart,
      quiet_end: quietEnd,
    }
  }
  return {
    name,
    task: 'operations',
    report_currencies: [],
    timezone,
    frequency: form.frequency,
    local_time: form.local_time,
    weekday,
    month_day: monthDay,
    lookback_days: lookback,
    channel,
    data_identity: form.data_identity,
    currency,
    rule_revision_id: ruleRevision,
    max_age_hours: maxAge,
    min_quantity: quantity,
    max_margin_percent: margin,
    quiet_start: quietStart,
    quiet_end: quietEnd,
  }
}
export type ScheduleGate = Record<ScheduleAction | 'check', boolean>
export function scheduleGates(
  row: Pick<ScheduleRow, 'status'> | undefined,
): ScheduleGate {
  const status = row?.status ?? ''
  if (status === 'revoked')
    return {
      pause: false,
      resume: false,
      revoke: false,
      edit: false,
      check: false,
    }
  return {
    pause: status === 'active',
    resume: status === 'paused',
    revoke: true,
    edit: true,
    check: status === 'active',
  }
}
/** Server refuses a manual run while paused; the button must not offer it. */
export function manualCheckReady(
  row: Pick<ScheduleRow, 'status' | 'version'> | undefined,
  version: number,
): boolean {
  return !!row && row.status === 'active' && row.version === version
}
export function notificationReady(
  item: Pick<Occurrence, 'read_at' | 'notify_at'>,
  now: number,
): boolean {
  if (item.read_at) return false
  const notify = Date.parse(item.notify_at)
  return Number.isFinite(notify) && notify <= now
}
export function createSchedulePayload(
  requestId: string,
  config: ScheduleConfig,
  confirmed: boolean,
): Record<string, unknown> {
  if (!requestId) throw new Error('缺少请求标识，请重新进入页面。')
  if (!confirmed) throw new Error('请确认计划范围和站内通知。')
  return { request_id: requestId, config, confirmed: true }
}
export function scheduleActionPayload(
  row: Pick<ScheduleRow, 'version'>,
  action: ScheduleAction,
  config: ScheduleConfig | undefined,
  confirmed: boolean,
): Record<string, unknown> {
  if (!Number.isInteger(row.version) || row.version < 1)
    throw new Error('计划版本无效，请刷新。')
  if (action === 'edit') {
    if (!config) throw new Error('请填写完整计划配置。')
    if (!confirmed) throw new Error('修改计划前请重新确认范围。')
    return { version: row.version, action, config, confirmed: true }
  }
  if (action === 'resume') {
    if (!confirmed) throw new Error('恢复计划前请重新确认范围。')
    return { version: row.version, action, confirmed: true }
  }
  return { version: row.version, action, confirmed: false }
}
export function manualCheckPayload(
  row: Pick<ScheduleRow, 'version'>,
  requestId: string,
): Record<string, unknown> {
  if (!requestId) throw new Error('缺少请求标识，请重新进入页面。')
  if (!Number.isInteger(row.version) || row.version < 1)
    throw new Error('计划版本无效，请刷新。')
  return { request_id: requestId, version: row.version }
}
export function scheduleSummary(config: ScheduleConfig): string {
  const parts: string[] = []
  if (config.task === 'report')
    parts.push(
      `经营报表 · ${config.report_currencies.join('、') || '全部币种分别统计'}`,
    )
  else
    parts.push(
      `${config.channel} · ${config.currency} · 回看 ${config.lookback_days} 天 · 规则 #${config.rule_revision_id}`,
    )
  if (config.quiet_start !== null && config.quiet_end !== null)
    parts.push(
      `免打扰 ${config.quiet_start}:00–${config.quiet_end}:00（${config.timezone}）`,
    )
  return parts.join(' · ')
}
export function scheduleCycleText(config: ScheduleConfig): string {
  const base = `${frequencyLabels[config.frequency] ?? config.frequency} ${config.local_time} ${config.timezone}`
  if (config.frequency === 'weekly')
    return `${base} · ${weekdayLabels[config.weekday] ?? config.weekday}`
  if (config.frequency === 'monthly')
    return `${base} · 每月 ${config.month_day} 日`
  return base
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
