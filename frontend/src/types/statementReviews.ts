import type { StatementReconciliation } from './statements'

export const reviewOutcomes = {
  consistent: '本窗口费用一致',
  differences_recorded: '金额差异已说明 · 处理待跟进',
  pending: '仍待核对',
}
export const reviewStatuses = {
  active: '当前有效',
  stale: '依据已变化 · 待重核',
  withdrawn: '已撤销',
  cleared: '已清除',
}
export interface ReviewConclusion {
  outcome: keyof typeof reviewOutcomes
  note: string
}
export interface ReviewSnapshot {
  conclusion: ReviewConclusion
  result: StatementReconciliation
  expense_revision: number
  blockers: string[]
}
export interface ReviewDraft {
  scope: StatementReconciliation['scope']
  review_id: number | null
  version: number
  conclusion: ReviewConclusion
}
export interface ReviewPreview {
  preview_hash: string
  snapshot: ReviewSnapshot
}
export interface ReviewWrite extends ReviewDraft {
  preview_hash: string
  request_id: string
  confirm: true
}
export interface ReviewSaved {
  id: number
  shop_id: number
  data_identity: ReviewDraft['scope']['data_identity']
  channel: ReviewDraft['scope']['channel']
  status: keyof typeof reviewStatuses
  version: number
  content_version: number
  created_at: string
  snapshot: ReviewSnapshot | null
  history: {
    version: number
    action: string
    conclusion: ReviewConclusion | null
    created_at: string
  }[]
}

export interface ReviewCurrent {
  record: ReviewSaved
  preview: ReviewPreview | null
}
