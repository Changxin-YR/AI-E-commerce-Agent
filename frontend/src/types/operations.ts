import type { AnalysisScope, SourceReference } from './analytics'

export interface OperationScope extends AnalysisScope {
  rule_revision_id?: number
  intent: 'low_margin'
  channel: string
  max_age_hours: number
}
export interface OperationContext {
  preview_hash: string
  preview: {
    source_revision: number
    branches: { name: string; status: string; count: number; reason: string }[]
    findings: { kind: string }[]
  }
}
export interface OperationRun {
  id: number
  shop_id: number
  scope: OperationScope
  source_revision: number
  source_status: string
  created_at: string
  valid_until: string | null
  snapshot: {
    engine: 'local_rules'
    model_status: 'not_configured'
    branches: { name: string; status: string; count: number; reason: string }[]
    task_ids: number[]
    sources: SourceReference[]
    data_as_of: string
    created_candidates: number
    reused_candidates: number
  } | null
}
export type TaskAction = 'approve' | 'reject' | 'ignore' | 'defer' | 'complete' | 'reopen' | 'edit'
export interface OperationTask {
  id: number
  shop_id: number
  kind: string
  status: string
  source_status: string
  version: number
  owner_id: number
  risk: 'R1'
  external_status: 'not_submitted'
  note: string
  due_at: string | null
  created_at: string
  snapshot: {
    object_label: string
    title: string
    severity: string
    basis: string
    advice: string
    impact: string
    facts: Record<string, string>
    sources: SourceReference[]
    valid_until: string | null
  } | null
  history: {
    action: string
    from_status: string
    to_status: string
    version: number
    created_at: string
    note: string | null
    due_at: string | null
  }[]
}
export const taskLabels: Record<string, string> = {
  pending_approval: '待审批',
  open: '待处理',
  deferred: '已延期',
  completed: '已完成',
  ignored: '已忽略',
  rejected: '已拒绝',
  none: '尚未创建',
}
export const sourceLabels: Record<string, string> = {
  current: '来源有效',
  stale: '需重新检查',
  cleared: '来源已清除',
}
