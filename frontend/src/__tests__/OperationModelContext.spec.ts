import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import OperationModelContext from '@/components/OperationModelContext.vue'
import OperationNarrative from '@/components/OperationNarrative.vue'
import { operationsApi } from '@/api/operations'
import type { OperationContext, OperationScope } from '@/types/operations'

vi.mock('@/api/operations', () => ({ operationsApi: { preview: vi.fn() } }))
const scope: OperationScope = {
  start_at: '2026-10-07T00:00:00Z',
  end_at: '2026-10-08T00:00:00Z',
  timezone: 'UTC',
  currency: 'USD',
  data_identity: 'synthetic',
  intent: 'low_margin',
  channel: 'generic',
  max_age_hours: 24,
  min_quantity: 1,
  max_margin_percent: '20',
}
const context: OperationContext = {
  preview_hash: 'synthetic-hash',
  preview: {
    source_revision: 3,
    findings: [{ kind: 'order_review' }],
    branches: [{ name: '订单履约核对', count: 1, status: 'partial', reason: '当前状态未知' }],
  },
}
it('discards late preview after switching scope and clears consent on failure', async () => {
  let release: (value: OperationContext) => void = () => undefined
  vi.mocked(operationsApi.preview)
    .mockReturnValueOnce(
      new Promise((resolve) => {
        release = resolve
      }),
    )
    .mockRejectedValueOnce(new Error('Unavailable'))
  const wrapper = mount(OperationModelContext, { props: { shop: 1, scope, disabled: false } })
  await wrapper.setProps({ scope: { ...scope, channel: 'amazon' } })
  await flushPromises()
  release(context)
  await flushPromises()
  expect(wrapper.emitted('change')?.every((event) => event[0] === null)).toBe(true)
  expect(wrapper.text()).not.toContain('订单履约核对')
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
})
it('binds loaded hash and removes it immediately on refresh', async () => {
  vi.mocked(operationsApi.preview)
    .mockResolvedValueOnce(context)
    .mockRejectedValueOnce(new Error('Unavailable'))
  const wrapper = mount(OperationModelContext, { props: { shop: 1, scope, disabled: false } })
  await flushPromises()
  expect(wrapper.emitted('change')?.slice(-1)[0]).toEqual(['synthetic-hash'])
  expect(wrapper.text()).toContain('部分检查')
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(wrapper.emitted('change')?.slice(-1)[0]).toEqual([null])
  expect(wrapper.text()).not.toContain('订单履约核对')
})
it('shows missing branches, candidate counts and review advice as escaped text', () => {
  const wrapper = mount(OperationNarrative, {
    props: {
      value: {
        branches: [
          {
            id: 'branch_1',
            name: '库存阈值',
            count: 0,
            status: 'not_checked',
            reason: '<script>unknown</script>',
          },
        ],
        candidate_counts: [{ kind: 'order_review', label: '来源履约状态待核对', count: 1 }],
        checks: [{ id: 'coverage', text: '核对来源覆盖' }],
        next_action: 'finish',
        composition: '模型组织概览',
      },
    },
  })
  expect(wrapper.text()).toContain('库存阈值 · 未检查')
  expect(wrapper.text()).toContain('没有生成异常候选')
  expect(wrapper.text()).toContain('<script>unknown</script>')
  expect(wrapper.find('script').exists()).toBe(false)
})
