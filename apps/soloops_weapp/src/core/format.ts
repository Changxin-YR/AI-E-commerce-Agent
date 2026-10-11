/**
 * 展示格式化：金额按服务端 Decimal 字符串透传，时间按显式 IANA 业务时区显示。
 * 未知值一律显示“未知”，不得回落到 0 或猜测值。
 */

export const UNKNOWN_TEXT = '未知'

/** 字段值展示：null / undefined / 空串统一为“未知”。 */
export function factText(value: unknown): string {
  if (value === null || value === undefined) return UNKNOWN_TEXT
  if (typeof value === 'string') return value.trim() === '' ? UNKNOWN_TEXT : value
  if (typeof value === 'number') return Number.isFinite(value) ? `${value}` : UNKNOWN_TEXT
  if (typeof value === 'boolean') return value ? '是' : '否'
  return `${value}`
}

/** 可空文本：允许页面自行决定占位。 */
export function textOr(value: unknown, fallback: string): string {
  if (value === null || value === undefined) return fallback
  const text = `${value}`
  return text.trim() === '' ? fallback : text
}

/**
 * 金额：服务端返回 Decimal 字符串，客户端只做拼接，绝不用浮点重新汇总。
 * 缺金额时返回“未知”，缺币种时不臆造币种。
 */
export function moneyText(amount: unknown, currency?: unknown): string {
  if (amount === null || amount === undefined || `${amount}`.trim() === '') return UNKNOWN_TEXT
  const currencyText = currency === null || currency === undefined ? '' : `${currency}`.trim()
  return currencyText === '' ? `${amount}` : `${amount} ${currencyText}`
}

/** 只保留数字/小数点/负号，供十进制输入校验使用（不做浮点转换）。 */
export function isDecimalInput(value: string): boolean {
  return /^-?\d+(\.\d+)?$/.test(value.trim())
}

const INSTANT_PATTERN =
  /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})/g
const INSTANT_EXACT =
  /^(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?(Z|[+-]\d{2}:\d{2})$/

function pad(value: number): string {
  return `${value}`.padStart(2, '0')
}

/** 解析带时区偏移的 ISO 时间为 UTC 毫秒；格式不合法返回 null（不猜测）。 */
export function parseInstant(text: string): number | null {
  const match = INSTANT_EXACT.exec(text.trim())
  if (!match) return null
  const [, day, hour, minute, second = '0', fraction = '0', offset] = match
  const [year, month, date] = day.split('-').map(Number)
  const hours = Number(hour)
  const minutes = Number(minute)
  const seconds = Number(second)
  if (hours > 23 || minutes > 59 || seconds > 59) return null
  let offsetMinutes = 0
  if (offset !== 'Z') {
    const sign = offset.startsWith('-') ? -1 : 1
    const offsetHours = Number(offset.slice(1, 3))
    const offsetRest = Number(offset.slice(4))
    if (offsetHours > 23 || offsetRest > 59) return null
    offsetMinutes = sign * (offsetHours * 60 + offsetRest)
  }
  const millis = Number(fraction.padEnd(3, '0').slice(0, 3))
  const utc = Date.UTC(year, month - 1, date, hours, minutes, seconds, millis)
  if (Number.isNaN(utc)) return null
  return utc - offsetMinutes * 60000
}

function offsetText(minutes: number): string {
  const sign = minutes < 0 ? '-' : '+'
  const abs = Math.abs(minutes)
  return `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
}

interface ZoneParts {
  year: number
  month: number
  day: number
  hour: number
  minute: number
  second: number
}

/**
 * 用运行时 Intl 读取 IANA 时区的本地时刻。
 * 小程序环境缺少 Intl 或时区不支持时返回 null，由调用方标注“（原始时间）”。
 */
function zoneParts(utcMillis: number, zone: string): ZoneParts | null {
  const formatter = createZoneFormatter(zone)
  if (!formatter) return null
  try {
    const parts = formatter.formatToParts(new Date(utcMillis))
    const picked: Record<string, number> = {}
    for (const part of parts) {
      if (part.type === 'literal') continue
      picked[part.type] = Number(part.value)
    }
    if (!Number.isFinite(picked.year) || !Number.isFinite(picked.month)) return null
    return {
      year: picked.year,
      month: picked.month,
      day: picked.day,
      // 部分引擎在 hour12=false 时把午夜输出为 24。
      hour: picked.hour === 24 ? 0 : picked.hour,
      minute: picked.minute,
      second: picked.second ?? 0,
    }
  } catch {
    return null
  }
}

const formatterCache = new Map<string, Intl.DateTimeFormat | null>()

function createZoneFormatter(zone: string): Intl.DateTimeFormat | null {
  if (formatterCache.has(zone)) return formatterCache.get(zone) ?? null
  let formatter: Intl.DateTimeFormat | null = null
  if (zone.trim() !== '' && typeof Intl !== 'undefined' && typeof Intl.DateTimeFormat === 'function') {
    try {
      formatter = new Intl.DateTimeFormat('en-US', {
        timeZone: zone.trim(),
        hour12: false,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    } catch {
      formatter = null
    }
  }
  formatterCache.set(zone, formatter)
  return formatter
}

/** 该时区在给定时刻的 UTC 偏移分钟数；无法计算返回 null。 */
export function zoneOffsetMinutes(utcMillis: number, zone: string): number | null {
  const parts = zoneParts(utcMillis, zone)
  if (!parts) return null
  const asUtc = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
    parts.second,
  )
  const raw = (asUtc - utcMillis) / 60000
  return Math.round(raw)
}

/** 单条时间展示：2026-10-11 09:00:00 (UTC+08:00 · Asia/Shanghai)。 */
export function displayInstant(value: string, zone: string): string | null {
  const utcMillis = parseInstant(value)
  if (utcMillis === null) return null
  const parts = zoneParts(utcMillis, zone)
  if (!parts) return null
  const offset = zoneOffsetMinutes(utcMillis, zone)
  if (offset === null) return null
  const day = `${parts.year}-${pad(parts.month)}-${pad(parts.day)}`
  const clock = `${pad(parts.hour)}:${pad(parts.minute)}:${pad(parts.second)}`
  return `${day} ${clock} (UTC${offsetText(offset)} · ${zone})`
}

/**
 * 文本中的 ISO 时间按业务时区重排；无法换算时保留原值并标注“（原始时间）”。
 * 与 Flutter businessTimeText 行为一致。
 */
export function businessTimeText(value: unknown, zone: string): string {
  if (value === null || value === undefined || `${value}` === '') return UNKNOWN_TEXT
  const text = `${value}`
  return text.replace(INSTANT_PATTERN, (match) => {
    const rendered = displayInstant(match, zone)
    return rendered === null ? `${match}（原始时间）` : rendered
  })
}

/** 只显示日期部分（业务时区）；时区不可用时保留原值。 */
export function businessDateText(value: unknown, zone: string): string {
  if (value === null || value === undefined || `${value}` === '') return UNKNOWN_TEXT
  const text = `${value}`
  const rendered = displayInstant(text, zone)
  return rendered === null ? text : rendered.slice(0, 10)
}

/** 业务时区下的今天，YYYY-MM-DD；无法确定时返回 null（不猜测）。 */
export function todayInZone(zone: string): string | null {
  const now = Date.now()
  const parts = zoneParts(now, zone)
  if (!parts) return null
  return `${parts.year}-${pad(parts.month)}-${pad(parts.day)}`
}

/** 业务时区下的当前时刻，含偏移的 ISO 字符串；无法确定时返回 null。 */
export function nowIsoInZone(zone: string): string | null {
  return isoInZone(Date.now(), zone)
}

/** 把 UTC 毫秒按业务时区渲染成带偏移的 ISO 字符串；无法确定时返回 null。 */
export function isoInZone(utcMillis: number, zone: string): string | null {
  const parts = zoneParts(utcMillis, zone)
  const offset = zoneOffsetMinutes(utcMillis, zone)
  if (!parts || offset === null) return null
  const day = `${parts.year}-${pad(parts.month)}-${pad(parts.day)}`
  const clock = `${pad(parts.hour)}:${pad(parts.minute)}:${pad(parts.second)}`
  return `${day}T${clock}${offsetText(offset)}`
}

/** 取 ISO 时间在业务时区下的日历日。 */
export function isoDay(value: string, zone: string): string | null {
  const utcMillis = parseInstant(value)
  if (utcMillis === null) return null
  const parts = zoneParts(utcMillis, zone)
  if (!parts) return null
  return `${parts.year}-${pad(parts.month)}-${pad(parts.day)}`
}

/** 取 ISO 时间在业务时区下的时刻 HH:mm。 */
export function isoClock(value: string, zone: string): string | null {
  const utcMillis = parseInstant(value)
  if (utcMillis === null) return null
  const parts = zoneParts(utcMillis, zone)
  if (!parts) return null
  return `${pad(parts.hour)}:${pad(parts.minute)}`
}

/** 在 ISO 时间上加减天数，保持绝对时刻不变。 */
export function shiftIso(value: string, days: number, zone: string): string | null {
  const utcMillis = parseInstant(value)
  if (utcMillis === null) return null
  return isoInZone(utcMillis + days * 86400000, zone)
}

/** 校验 YYYY-MM-DD 是否为真实存在的日期。 */
export function isValidDate(text: string): boolean {
  const value = text.trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  if (month < 1 || month > 12 || day < 1) return false
  const date = new Date(Date.UTC(year, month - 1, day))
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  )
}

/** 校验带偏移的 ISO 时间是否合法。 */
export function isValidInstant(text: string): boolean {
  return parseInstant(text) !== null
}

/**
 * 由业务时区的日历日 + 时钟时间构造带偏移的 ISO 字符串。
 * 采用两遍偏移法处理夏令时；构造结果会再次校验，无法确定时返回 null。
 */
export function zonedIsoFromParts(day: string, clock: string, zone: string): string | null {
  if (!isValidDate(day) || !/^\d{2}:\d{2}$/.test(clock)) return null
  const [year, month, date] = day.split('-').map(Number)
  const [hour, minute] = clock.split(':').map(Number)
  if (hour > 23 || minute > 59) return null
  const naive = Date.UTC(year, month - 1, date, hour, minute, 0)
  const first = zoneOffsetMinutes(naive, zone)
  if (first === null) return null
  let candidate = naive - first * 60000
  const second = zoneOffsetMinutes(candidate, zone)
  if (second !== null && second !== first) {
    candidate = naive - second * 60000
  }
  const parts = zoneParts(candidate, zone)
  if (
    !parts ||
    parts.year !== year ||
    parts.month !== month ||
    parts.day !== date ||
    parts.hour !== hour ||
    parts.minute !== minute
  ) {
    // 夏令时跳变导致该本地时间不存在，交由调用方提示另选时间。
    return null
  }
  const offset = zoneOffsetMinutes(candidate, zone)
  if (offset === null) return null
  return `${day}T${pad(hour)}:${pad(minute)}:00${offsetText(offset)}`
}

/** 计数展示：缺值显示“—”，不显示 0 冒充真实计数。 */
export function countText(value: unknown): string {
  if (value === null || value === undefined) return '—'
  return `${value}`
}

/** 截断过长文本，保留可读摘要。 */
export function shorten(value: unknown, limit: number): string {
  const text = value === null || value === undefined ? '' : `${value}`
  return text.length <= limit ? text : `${text.slice(0, limit)}…`
}
