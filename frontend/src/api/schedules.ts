import { request } from './client'

export interface ScheduleConfig {
  name: string
  task: 'operations' | 'report'
  report_currencies: string[]
  timezone: string
  frequency: 'daily' | 'weekly' | 'monthly'
  local_time: string
  weekday: number
  month_day: number
  lookback_days: number
  channel: string
  data_identity: string
  currency: string
  rule_revision_id: number
  max_age_hours: number
  min_quantity: number
  max_margin_percent: string
  quiet_start: number | null
  quiet_end: number | null
}
export interface Schedule {
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
  task: 'operations' | 'report'
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
export type ScheduleAction = 'pause' | 'resume' | 'revoke' | 'edit'
const root = (shop: number) => `/shops/${shop}/schedules`
export const schedulesApi = {
  list: (shop: number) => request<Schedule[]>(root(shop)),
  status: (shop: number) => request<ScheduleStatus>(`${root(shop)}/status`),
  create: (shop: number, request_id: string, config: ScheduleConfig) =>
    request<Schedule>(root(shop), {
      method: 'POST',
      body: JSON.stringify({ request_id, config, confirmed: true }),
    }),
  act: (row: Schedule, action: ScheduleAction, config?: ScheduleConfig) =>
    request<Schedule>(`${root(row.shop_id)}/${row.id}`, {
      method: 'POST',
      body: JSON.stringify({
        version: row.version,
        action,
        config,
        confirmed: action === 'edit' || action === 'resume',
      }),
    }),
  check: (row: Schedule, request_id: string) =>
    request<Occurrence>(`${root(row.shop_id)}/${row.id}/check`, {
      method: 'POST',
      body: JSON.stringify({ version: row.version, request_id }),
    }),
  history: (shop: number, unread: boolean, before?: number) =>
    request<Occurrence[]>(
      `${root(shop)}/history?unread=${unread}${before ? `&before=${before}` : ''}`,
    ),
  read: (shop: number, id: number) =>
    request<Occurrence>(`${root(shop)}/history/${id}/read`, { method: 'POST' }),
}
export const scheduleLabels: Record<string, string> = {
  active: '已启用',
  paused: '已暂停',
  revoked: '已撤销',
  waiting_approval: '等待审批',
  succeeded: '检查完成',
  blocked: '检查受阻',
  missed: '错过周期',
  daily: '每天',
  weekly: '每周',
  monthly: '每月',
  ready: '等待继续',
  circuit_open: '读取失败',
  cancelled: '已取消',
}
