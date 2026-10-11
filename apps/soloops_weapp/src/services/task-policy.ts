import type { OperationTask, TaskAction } from './operation-types'

const allowed: Record<TaskAction, string[]> = {
  approve: ['pending_approval'],
  reject: ['pending_approval'],
  ignore: ['pending_approval', 'open', 'deferred'],
  defer: ['open', 'deferred'],
  complete: ['open', 'deferred'],
  reopen: ['completed', 'ignored', 'rejected', 'deferred'],
  edit: [
    'pending_approval',
    'open',
    'deferred',
    'completed',
    'ignored',
    'rejected',
  ],
  record_evidence: ['open', 'deferred', 'completed'],
  wait_source: ['open', 'deferred', 'completed'],
  recheck: ['open', 'deferred', 'completed'],
}
export const actionLabels: Record<TaskAction, string> = {
  approve: '批准并创建待办',
  reject: '拒绝候选',
  ignore: '忽略事项',
  defer: '延期至截止时间',
  complete: '完成核对',
  reopen: '重新打开',
  edit: '保存备注与截止',
  record_evidence: '登记人工操作证据',
  wait_source: '等待来源更新',
  recheck: '按原事项复检',
}
export function taskActions(
  task: Pick<OperationTask, 'status' | 'source_status' | 'snapshot'>,
): TaskAction[] {
  if (!task.snapshot || !['current', 'stale'].includes(task.source_status))
    return []
  return (Object.keys(allowed) as TaskAction[]).filter(
    (action) =>
      allowed[action].includes(task.status) &&
      (task.source_status === 'current' ||
        [
          'reject',
          'ignore',
          'reopen',
          'record_evidence',
          'wait_source',
          'recheck',
        ].includes(action)),
  )
}
export function queryString(
  values: Record<string, string | number | null | undefined>,
): string {
  return Object.entries(values)
    .filter(([, value]) => value != null && value !== '')
    .map(
      ([key, value]) =>
        `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`,
    )
    .join('&')
}
export function requestId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const n = Math.floor(Math.random() * 16)
    return (char === 'x' ? n : (n & 3) | 8).toString(16)
  })
}
