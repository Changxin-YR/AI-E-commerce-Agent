// Browser-local timezone is never used for business input.
export function localTime(value: string, timezone: string): string {
  if (!value) return ''
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) throw new Error('请填写有效时间。')
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const part = (type: string) => parts.find((p) => p.type === type)!.value
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}:${part('second')}`
}

export function resolveLocalTime(value: string, timezone: string): string {
  if (!value) return ''
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(value))
    throw new Error('请选择完整的日期与时间。')
  const normalized = value.length === 16 ? `${value}:00` : value
  const wall = Date.parse(`${normalized}Z`)
  if (!Number.isFinite(wall) || new Date(wall).toISOString().slice(0, 19) !== normalized)
    throw new Error('日期或时间无效。')
  // Gather offsets on both sides of a nearby transition (including half-hour DST
  // and date-line changes), then round-trip each candidate through the IANA zone.
  const offsets = new Set<number>()
  for (let hours = -48; hours <= 48; hours += 6) {
    const instant = wall + hours * 3600000
    offsets.add(Date.parse(`${localTime(new Date(instant).toISOString(), timezone)}Z`) - instant)
  }
  const matches = [...offsets]
    .map((offset) => new Date(wall - offset).toISOString())
    .filter((instant) => localTime(instant, timezone) === normalized)
  if (!matches.length) throw new Error('该时间在此时区不存在，请重新选择（夏令时或日期变更）。')
  if (matches.length > 1)
    throw new Error('该时间在此时区出现两次，请在高级输入中明确指定 ISO 时区偏移。')
  return matches[0]!
}

export function exactTimeError(value: string, timezone: string): string {
  if (!value) return ''
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})$/.test(value))
    return '高级时间须包含 Z 或明确偏移，例如 +08:00。'
  try {
    const wall = value.replace(/(?:Z|[+-]\d{2}:\d{2})$/, '').replace(/\.\d+$/, '')
    const normalized = wall.length === 16 ? `${wall}:00` : wall
    if (
      !Number.isFinite(Date.parse(value)) ||
      new Date(`${normalized}Z`).toISOString().slice(0, 19) !== normalized
    )
      return '日期或时间无效。'
    localTime(value, timezone)
    return ''
  } catch {
    return '请核对有效时间与 IANA 业务时区。'
  }
}
