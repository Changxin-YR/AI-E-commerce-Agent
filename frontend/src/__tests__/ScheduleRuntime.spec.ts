import { mount, RouterLinkStub } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ScheduleRuntime from '@/components/ScheduleRuntime.vue'
import type { Occurrence } from '@/api/schedules'

const latest: Occurrence = {
  id: 8,
  shop_id: 2,
  schedule_id: 3,
  schedule_version: 1,
  trigger: 'timer',
  scheduled_at: '2026-10-09T01:00:00Z',
  created_at: '2026-10-09T01:01:00Z',
  coalesced_from: '2026-10-07T01:00:00Z',
  execution_id: 11,
  task: 'operations',
  report_id: null,
  status: 'waiting_approval',
  reason: '',
  notify_at: '2026-10-09T04:00:00Z',
  read_at: '2026-10-09T05:00:00Z',
}
function render(value: Occurrence | null, worker = true) {
  return mount(ScheduleRuntime, {
    props: { worker, latest: value, timezone: 'Asia/Shanghai' },
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
}
describe('Schedule runtime evidence', () => {
  it('separates enabled configuration from evidence of automatic execution', () => {
    const wrapper = render(null)
    expect(wrapper.text()).toContain('尚无自动周期记录')
    expect(wrapper.text()).toContain('不代表持续在线')
    expect(wrapper.text()).toContain('API 关闭、电脑关机或休眠期间不运行')
    expect(wrapper.text()).toContain('暂停期间不补跑')
  })
  it('shows read and quiet-hour timer records with zoned times and actual progress link', () => {
    const wrapper = render(latest, false)
    expect(wrapper.text()).toContain('当前服务关闭自动调度')
    expect(wrapper.text()).toContain('保存时间：2026/10/9 09:01 (Asia/Shanghai)')
    expect(wrapper.text()).toContain('计划时刻：2026/10/9 09:00 (Asia/Shanghai)')
    expect(wrapper.text()).toContain('当次状态：等待审批')
    expect(wrapper.text()).toContain('较早周期已合并')
    expect(wrapper.getComponent(RouterLinkStub).props('to')).toEqual({
      path: '/agent',
      query: { shop: 2, execution: 11 },
    })
  })
  it('keeps missed cycles explicitly unexecuted and without execution links', () => {
    const wrapper = render({ ...latest, status: 'missed', execution_id: null })
    expect(wrapper.text()).toContain('当次状态：错过周期')
    expect(wrapper.text()).toContain('未执行，等待下一周期')
    expect(wrapper.findComponent(RouterLinkStub).exists()).toBe(false)
  })
})
