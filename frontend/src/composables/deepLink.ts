import { nextTick } from 'vue'
import type { Shop } from '@/types/identity'
import type { AnalysisScope } from '@/types/analytics'

type LinkedScope = Partial<AnalysisScope> & { max_age_hours?: number }
const channels = ['generic', 'shopify', 'amazon', 'other']

export function scopeQuery(scope: LinkedScope): Record<string, string> {
  const query: Record<string, string> = {}
  for (const key of [
    'start_at',
    'end_at',
    'timezone',
    'currency',
    'channel',
    'min_quantity',
    'max_margin_percent',
    'max_age_hours',
  ] as const) {
    const value = scope[key]
    if (value !== null && value !== undefined) query[key] = String(value)
  }
  if (scope.data_identity) query.identity = scope.data_identity
  return query
}

export function applyLinkedScope(
  scope: LinkedScope,
  query: Record<string, unknown>,
  includeStockAge = true,
): void {
  const invalid = () => {
    throw new Error('链接中的业务范围无效，请返回原事项重新打开。')
  }
  if (query.identity !== undefined) {
    if (query.identity !== 'synthetic' && query.identity !== 'user_import') invalid()
    scope.data_identity = query.identity as AnalysisScope['data_identity']
  }
  if (query.channel !== undefined) {
    if (typeof query.channel !== 'string' || !channels.includes(query.channel)) invalid()
    scope.channel = query.channel as string
  }
  for (const key of ['start_at', 'end_at'] as const) {
    const value = query[key]
    if (value === undefined) continue
    if (
      typeof value !== 'string' ||
      value.length > 40 ||
      !/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ||
      !Number.isFinite(Date.parse(value))
    )
      invalid()
    scope[key] = value as string
  }
  if (query.currency !== undefined) {
    if (
      typeof query.currency !== 'string' ||
      !['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD'].includes(query.currency)
    )
      invalid()
    scope.currency = query.currency as string
  }
  if (query.timezone !== undefined) {
    if (typeof query.timezone !== 'string' || query.timezone.length > 64) invalid()
    try {
      new Intl.DateTimeFormat('en', { timeZone: query.timezone as string })
    } catch {
      invalid()
    }
    scope.timezone = query.timezone as string
  }
  for (const key of ['min_quantity', 'max_age_hours'] as const) {
    if (query[key] === undefined) continue
    const value = query[key]
    if (
      typeof value !== 'string' ||
      !/^\d+$/.test(value) ||
      Number(value) < 1 ||
      Number(value) > (key === 'max_age_hours' ? 720 : 1000000)
    )
      invalid()
    if (key !== 'max_age_hours' || includeStockAge) scope[key] = Number(value)
  }
  if (query.max_margin_percent !== undefined) {
    const value = query.max_margin_percent
    if (
      typeof value !== 'string' ||
      !/^-?\d+(?:\.\d{1,2})?$/.test(value) ||
      Number(value) < -1000 ||
      Number(value) > 100
    )
      invalid()
    scope.max_margin_percent = value as string
  }
}

export function returnTaskQuery(
  query: Record<string, unknown>,
  currentShop?: number,
): Record<string, string> {
  if (currentShop !== undefined && linkedId(query.shop) !== currentShop) return {}
  const task = linkedId(query.return_task)
  return task ? { return_task: String(task) } : {}
}

export function linkedId(value: unknown): number | undefined {
  if (value === undefined) return undefined
  if (
    typeof value !== 'string' ||
    !/^[1-9]\d*$/.test(value) ||
    !Number.isSafeInteger(Number(value))
  )
    throw new Error('记录链接无效，请返回工作台重新打开。')
  return Number(value)
}

export function linkedShop(shops: Shop[], value: unknown): number {
  const id = linkedId(value)
  if (id !== undefined && !shops.some((shop) => shop.id === id))
    throw new Error('链接中的店铺不存在或无权访问。')
  return id ?? shops[0]?.id ?? 0
}

export async function revealRecord(id: string): Promise<void> {
  await nextTick()
  document.getElementById(id)?.scrollIntoView({ block: 'start' })
}
