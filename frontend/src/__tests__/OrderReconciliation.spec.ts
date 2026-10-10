import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import OrderReconciliationView from '@/views/OrderReconciliationView.vue'
import OrderReconciliationResult from '@/components/OrderReconciliationResult.vue'
import { orderReconciliationApi } from '@/api/orderReconciliation'
import { identityApi } from '@/api/identity'
import type { OrderReconciliation } from '@/types/orderReconciliation'

vi.mock('vue-router', () => ({ useRoute: () => ({ query: { shop: '1' } }) }))
vi.mock('@/api/identity', () => ({ identityApi: { shops: vi.fn() } }))
vi.mock('@/api/orderReconciliation', () => ({ orderReconciliationApi: { reconcile: vi.fn() } }))
const result: OrderReconciliation = {
  scope: {
    data_identity: 'synthetic',
    channel: 'generic',
    timezone: 'UTC',
    start_at: '2026-10-07T00:00:00Z',
    end_at: '2026-10-08T00:00:00Z',
    sale_basis: 'merchandise_after_discount',
    basis_note: '<img src=x onerror=alert(1)>',
  },
  source_revision: 2,
  calculated_at: '2026-10-09T00:00:00Z',
  coverage: 'unknown',
  orders: [],
  statements: [],
  checks: ['覆盖未知'],
  comparisons: [
    {
      order_id: 'ZERO',
      entry_type: 'sale',
      statement_ids: [],
      order_line_ids: [],
      status: 'matched',
      reasons: [],
      currency: 'USD',
      order_amount: '1.0001',
      difference: '0.0000',
    },
    {
      order_id: 'REFUND',
      entry_type: 'refund',
      statement_ids: [],
      order_line_ids: [],
      status: 'pending',
      reasons: ['refund_transaction_unknown'],
      currency: null,
      order_amount: null,
      difference: null,
    },
  ],
}
const wrappers: { unmount: () => void }[] = []
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(identityApi.shops).mockResolvedValue([
    {
      id: 1,
      name: 'Synthetic',
      code: 'test',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'UTC',
      connection_status: 'file_only',
    },
  ])
  vi.mocked(orderReconciliationApi.reconcile).mockResolvedValue(result)
})
afterEach(() => wrappers.splice(0).forEach((w) => w.unmount()))
async function view() {
  const wrapper = mount(OrderReconciliationView, {
    global: { stubs: { RouterLink: true, SupportSource: true } },
  })
  wrappers.push(wrapper)
  await flushPromises()
  return wrapper
}
it('defaults to unknown and requires evidence for a declared basis', async () => {
  const wrapper = await view()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(vi.mocked(orderReconciliationApi.reconcile).mock.calls[0]![1].sale_basis).toBe('unknown')
  await wrapper.get('#order-check-basis').setValue('merchandise_after_discount')
  expect(wrapper.findComponent(OrderReconciliationResult).exists()).toBe(false)
  await wrapper.get('form').trigger('submit')
  expect(orderReconciliationApi.reconcile).toHaveBeenCalledTimes(1)
  await wrapper.get('#order-check-note').setValue('Synthetic file columns')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(orderReconciliationApi.reconcile).toHaveBeenCalledTimes(2)
  await wrapper.get('#order-check-channel').setValue('amazon')
  expect((wrapper.get('#order-check-basis').element as HTMLSelectElement).value).toBe('unknown')
  expect(wrapper.find('#order-check-note').exists()).toBe(false)
  expect(wrapper.findComponent(OrderReconciliationResult).exists()).toBe(false)
})
it('hides previous results before a failed read', async () => {
  const wrapper = await view()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain('ZERO')
  vi.mocked(orderReconciliationApi.reconcile).mockRejectedValueOnce(new Error('Read failed'))
  await wrapper.get('form').trigger('submit')
  expect(wrapper.text()).not.toContain('ZERO')
  await flushPromises()
  expect(wrapper.text()).toContain('Read failed')
})
it('drops late reads after focus or scope changes and allows a fresh request', async () => {
  const wrapper = await view()
  let resolve!: (value: OrderReconciliation) => void
  vi.mocked(orderReconciliationApi.reconcile).mockReturnValueOnce(
    new Promise((r) => {
      resolve = r
    }),
  )
  await wrapper.get('form').trigger('submit')
  window.dispatchEvent(new Event('focus'))
  await flushPromises()
  await wrapper.get('#order-check-identity').setValue('synthetic')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain('ZERO')
  resolve({ ...result, comparisons: [] })
  await flushPromises()
  expect(wrapper.text()).toContain('ZERO')
  await wrapper.findAll('input[type=datetime-local]')[1]!.setValue('2026-10-08T00:00:00')
  expect(wrapper.findComponent(OrderReconciliationResult).exists()).toBe(false)
})
it('invalidates visible evidence and declaration on focus', async () => {
  const wrapper = await view()
  await wrapper.get('#order-check-basis').setValue('merchandise_after_discount')
  await wrapper.get('#order-check-note').setValue('source')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  window.dispatchEvent(new Event('focus'))
  await flushPromises()
  expect(wrapper.text()).not.toContain('ZERO')
  expect((wrapper.get('#order-check-basis').element as HTMLSelectElement).value).toBe('unknown')
})
it('filters unknown refunds, preserves zero decimals and escapes declarations', async () => {
  const wrapper = mount(OrderReconciliationResult, {
    props: { result, shopId: 1 },
    global: { stubs: { RouterLink: true, SupportSource: true } },
  })
  wrappers.push(wrapper)
  expect(wrapper.text()).toContain('差额 USD 0.0000')
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.text()).toContain('<img src=x onerror=alert(1)>')
  await wrapper.get('select').setValue('pending')
  expect(wrapper.findAll('article')).toHaveLength(1)
  expect(wrapper.get('article').text()).toContain('退款差额未知')
  expect(wrapper.get('article').text()).not.toContain('差额 USD')
})
it('shows empty coverage as unknown and can recover shop initialization', async () => {
  vi.mocked(identityApi.shops).mockRejectedValueOnce(new Error('Shops unavailable'))
  const wrapper = await view()
  expect(wrapper.text()).toContain('Shops unavailable')
  await wrapper.get('button').trigger('click')
  await flushPromises()
  vi.mocked(orderReconciliationApi.reconcile).mockResolvedValueOnce({ ...result, comparisons: [] })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain('无法判断实际销售或退款是否发生')
})
