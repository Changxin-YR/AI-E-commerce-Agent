export interface WorkItem {
  kind: string
  id: number
  target_id: number
  shop_id: number | null
  shop_name: string
  timezone: string
  data_identity: string | null
  channel: string | null
  status: string
  source_status: string
  bucket: string
  view: string | null
  business_state: string | null
  review_current: boolean
  label: string
  detail: string
  created_at: string
  due_at: string | null
  risk: string
  path: string
  query: Record<string, string>
}
export interface WorkPage {
  items: WorkItem[]
  recent_runs: WorkItem[]
  counts: Record<string, number>
  view_counts: Record<string, number>
  next_cursor: string | null
  read_at: string
}
export const workViews: Record<string, string> = {
  attention: '待我处理',
  ai_completed: 'AI 已完成',
  update_data: '需要更新数据',
}
export const workKinds: Record<string, string> = {
  operation_task: '运营待办',
  agent: 'Agent 执行',
  listing: 'Listing 草稿',
  reply: '客服草稿',
  analysis_todo: '分析核对待办',
  operation_run: '运营检查',
  analysis: '分析报告',
  overview: '经营摘要',
  authorization: 'R1 预授权',
  outbound: 'R2 测试邮件',
}
export const workBuckets: Record<string, string> = {
  pending: '待处理',
  approval: '待审阅',
  failed: '失败 / 阻断',
  unknown: '结果未知',
  stale: '需更新来源',
  history: '存档 / 已记录',
}
