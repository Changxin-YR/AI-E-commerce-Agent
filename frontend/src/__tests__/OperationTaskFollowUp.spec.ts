import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import OperationTaskFollowUp from '@/components/OperationTaskFollowUp.vue'
import OperationTaskReview from '@/components/OperationTaskReview.vue'
import { operationsApi } from '@/api/operations'
import type { OperationTask } from '@/types/operations'

vi.mock('@/api/operations', () => ({ operationsApi: { change: vi.fn() } }))
const task: OperationTask = {
  id: 1,
  shop_id: 2,
  owner_id: 3,
  kind: 'low_inventory',
  status: 'open',
  source_status: 'current',
  version: 2,
  note: '',
  due_at: null,
  created_at: '2026-10-10T00:00:00Z',
  risk: 'R1',
  external_status: 'not_submitted',
  history: [],
  snapshot: {
    object_label: 'SKU-1',
    title: '库存核对',
    severity: 'attention',
    basis: '',
    advice: '',
    impact: '',
    facts: {},
    sources: [],
    valid_until: null,
  },
}
function button(wrapper: VueWrapper, name: string) {
  return wrapper.findAll('button').find((item) => item.text() === name)!
}
beforeEach(() => vi.resetAllMocks())

it('requires renewed self-report confirmation, preserves input on failure and gates surrounding actions', async () => {
  const wrapper = mount(OperationTaskReview, {
    props: { task, timezone: 'Asia/Shanghai' },
    global: { stubs: { RouterLink: true } },
  })
  await wrapper.get('#review-description').setValue('Synthetic external check')
  await wrapper.get('#review-reference').setValue('<script>receipt</script>')
  await wrapper.get('#review-occurred').setValue('2026-10-10T01:00:00Z')
  expect(wrapper.emitted('dirty')?.slice(-1)[0]).toEqual([true])
  expect(button(wrapper, '标记完成').element.matches(':disabled')).toBe(true)
  await wrapper.get('input[type="checkbox"]').setValue(true)
  await wrapper.get('#review-reference').setValue('Reference-2')
  expect(button(wrapper, '登记操作证据').attributes('disabled')).toBeDefined()
  await wrapper.get('input[type="checkbox"]').setValue(true)
  vi.mocked(operationsApi.change).mockRejectedValueOnce(new Error('连接中断'))
  await button(wrapper, '登记操作证据').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('连接中断')
  expect((wrapper.get('#review-reference').element as HTMLInputElement).value).toBe('Reference-2')
  let release!: (value: OperationTask) => void
  vi.mocked(operationsApi.change).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        release = resolve
      }),
  )
  await button(wrapper, '登记操作证据').trigger('click')
  expect(button(wrapper, '标记完成').element.matches(':disabled')).toBe(true)
  expect(button(wrapper, '按原事项复检新来源').element.matches(':disabled')).toBe(true)
  expect(wrapper.emitted('working')?.slice(-1)[0]).toEqual([true])
  release({ ...task, version: 3, business_state: 'evidence_recorded' })
  await flushPromises()
  expect(vi.mocked(operationsApi.change).mock.calls[0]).toEqual(
    vi.mocked(operationsApi.change).mock.calls[1],
  )
  expect(wrapper.emitted('updated')).toHaveLength(1)
  expect(wrapper.emitted('working')?.slice(-1)[0]).toEqual([false])
})

it('ignores late responses after switching the task and supports rechecks on replaced original sources', async () => {
  let release!: (value: OperationTask) => void
  vi.mocked(operationsApi.change).mockImplementation(
    () =>
      new Promise((resolve) => {
        release = resolve
      }),
  )
  const wrapper = mount(OperationTaskFollowUp, {
    props: { task: { ...task, source_status: 'stale' }, timezone: 'UTC', disabled: false },
  })
  await button(wrapper, '按原事项复检新来源').trigger('click')
  expect(operationsApi.change).toHaveBeenCalledWith(2, 1, 2, 'recheck', '', null, undefined)
  await wrapper.setProps({ task: { ...task, id: 4 } })
  release({ ...task, business_state: 'resolved' })
  await flushPromises()
  expect(wrapper.emitted('updated')).toBeUndefined()
  expect(wrapper.text()).not.toContain('新有效证据支持已解决')
  expect(button(wrapper, '按原事项复检新来源').element.matches(':disabled')).toBe(false)
})

it('separates completed checks, stale conclusions and cleared evidence, escaping self-reported text', async () => {
  const wrapper = mount(OperationTaskFollowUp, {
    props: { task: { ...task, status: 'completed' }, timezone: 'UTC', disabled: false },
  })
  expect(wrapper.text()).toContain('已核对待外部处理')
  await wrapper.setProps({
    task: {
      ...task,
      business_state: 'awaiting_source',
      review_current: false,
      review: {
        state: 'resolved',
        evidence: {
          description: '<script>never execute</script>',
          evidence_ref: 'ref',
          occurred_at: task.created_at,
          recorded_at: task.created_at,
          recorded_by: 3,
          provenance: 'seller_reported',
        },
        recheck: {
          state: 'resolved',
          reason: 'Synthetic source',
          checked_at: task.created_at,
          source_revision: 1,
          valid_until: null,
          facts: {},
          sources: [],
        },
      },
    },
  })
  expect(wrapper.get('h3').text()).toContain('待来源更新复检')
  expect(wrapper.text()).toContain('存档结论已因来源')
  expect(wrapper.text()).toContain('<script>never execute</script>')
  expect(wrapper.find('script').exists()).toBe(false)
  await wrapper.setProps({
    task: { ...task, snapshot: null, review: null, business_state: 'cleared' },
  })
  expect(wrapper.findAll('button')).toHaveLength(0)
  expect(wrapper.text()).not.toContain('never execute')
})
