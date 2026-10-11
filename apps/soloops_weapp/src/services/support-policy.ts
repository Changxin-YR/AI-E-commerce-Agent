import type { ReplyDraft } from './support-types'

export function replyActions(
  item: ReplyDraft,
  dirty: boolean,
  language: string,
) {
  const known = ['draft', 'human_review', 'archived'].includes(item.status)
  const current = known && item.source_status === 'current' && !!item.snapshot
  const persisted = current && !dirty && !!item.snapshot?.reply.trim()
  return {
    edit: current && item.status !== 'archived',
    handoff: current && !dirty && item.status === 'draft',
    archive:
      known &&
      !dirty &&
      ['current', 'stale'].includes(item.source_status) &&
      item.status !== 'archived',
    reopen: current && !dirty && item.status === 'archived',
    review: persisted,
    deliver:
      persisted &&
      item.reviewed_version === item.version &&
      !!item.reviewed_at &&
      item.reviewed_language === language,
  }
}

export function awareTimestamp(value: string): string {
  if (
    !/(Z|[+-]\d{2}:\d{2})$/i.test(value) ||
    !Number.isFinite(Date.parse(value))
  )
    throw new Error('时间须包含时区，例如 2026-10-11T09:00:00+08:00。')
  return new Date(value).toISOString()
}
