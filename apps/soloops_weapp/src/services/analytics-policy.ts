import type { AnalysisScope, CostHistory, CostWrite } from './analytics-types'
import { awareTimestamp } from './support-policy.ts'

export function linkedAnalysisScope(
  scope: AnalysisScope,
  query: Record<string, string>,
): AnalysisScope {
  const value = { ...scope }
  for (const key of [
    'start_at',
    'end_at',
    'timezone',
    'currency',
    'channel',
    'max_margin_percent',
  ] as const)
    if (query[key] !== undefined) value[key] = query[key]
  if (query.min_quantity !== undefined)
    value.min_quantity = Number(query.min_quantity)
  if (query.identity !== undefined)
    value.data_identity = query.identity as AnalysisScope['data_identity']
  if (query.intent !== undefined)
    value.intent = query.intent as AnalysisScope['intent']
  if (
    !['synthetic', 'user_import'].includes(value.data_identity) ||
    (value.channel != null &&
      !['generic', 'shopify', 'amazon', 'other'].includes(value.channel)) ||
    !['summary', 'sales', 'low_margin'].includes(value.intent) ||
    !['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD'].includes(
      value.currency,
    )
  )
    throw new Error('链接中的分析范围无效，请返回原事项。')
  try {
    new Intl.DateTimeFormat('en', { timeZone: value.timezone })
  } catch {
    throw new Error('业务时区无效。')
  }
  return checkedAnalysisScope(value)
}

export function checkedAnalysisScope(scope: AnalysisScope): AnalysisScope {
  const start = awareTimestamp(scope.start_at),
    end = awareTimestamp(scope.end_at)
  const duration = Date.parse(end) - Date.parse(start)
  if (duration <= 0 || duration > 366 * 86400000)
    throw new Error('时间窗须为正且不超过366天，结束时间不含。')
  if (
    !Number.isInteger(scope.min_quantity) ||
    scope.min_quantity < 1 ||
    scope.min_quantity > 1000000
  )
    throw new Error('最低销量须为1–1000000整数。')
  if (
    !/^-?\d+(\.\d{1,2})?$/.test(scope.max_margin_percent) ||
    Number(scope.max_margin_percent) < -1000 ||
    Number(scope.max_margin_percent) > 100
  )
    throw new Error('毛利率上限须为-1000至100，最多两位小数。')
  return { ...scope, start_at: start, end_at: end }
}
export function costWrite(
  page: CostHistory,
  action: 'upsert' | 'revoke',
  content: NonNullable<CostWrite['content']>,
  id: string,
): CostWrite {
  if (!page.source_current || !content.confirmed)
    throw new Error('请核对当前订单来源并确认本次成本操作。')
  const base = {
    request_id: id,
    expected_version: page.version,
    expected_revision: page.source_revision,
    action,
  }
  if (action === 'revoke') return base
  if (
    !/^\d{1,14}(\.\d{1,4})?$/.test(content.unit_cost) ||
    !content.evidence_ref.trim()
  )
    throw new Error('请填写非负单位成本（最多四位小数）及凭据。')
  const time = awareTimestamp(content.evidence_at)
  if (new Date(time).getUTCFullYear() < 2000)
    throw new Error('凭据时间不得早于2000年。')
  return { ...base, content: { ...content, evidence_at: time } }
}
