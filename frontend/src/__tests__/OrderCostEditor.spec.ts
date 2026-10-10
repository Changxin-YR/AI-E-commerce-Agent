import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import OrderCostEditor from '@/components/OrderCostEditor.vue'
import AnalysisEvidence from '@/components/AnalysisEvidence.vue'
import { analyticsApi } from '@/api/analytics'
import type { AnalysisResult, CostHistory } from '@/types/analytics'

vi.mock('@/api/analytics', () => ({ analyticsApi: { costHistory: vi.fn(), writeCost: vi.fn() } }))
const history: CostHistory = {
  source_row_id: 9,
  source_batch_id: 2,
  source_current: true,
  source_revision: 4,
  order_id: 'O1',
  line_id: '1',
  sku: 'SYN',
  currency: 'USD',
  channel: 'generic',
  data_identity: 'synthetic',
  version: 0,
  history: [],
}
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(analyticsApi.costHistory).mockResolvedValue(history)
})

it('requires evidence and renewed confirmation, preserves UUID after unknown failure', async () => {
  const wrapper = mount(OrderCostEditor, {
    props: { shopId: 1, rowId: 9, timezone: 'Asia/Shanghai' },
  })
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('尚无历史成本凭据')
  const fields = wrapper.findAll('input')
  await fields[0]!.setValue('3.25')
  await wrapper.get('select').setValue('USD')
  await fields[1]!.setValue('Synthetic receipt')
  await fields[2]!.setValue('2026-10-06T08:00:00+08:00')
  expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  await wrapper.get('input[type="checkbox"]').setValue(true)
  await fields[0]!.setValue('4.5')
  expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  await wrapper.get('input[type="checkbox"]').setValue(true)
  vi.mocked(analyticsApi.writeCost)
    .mockRejectedValueOnce(new Error('连接中断'))
    .mockResolvedValueOnce({ ...history, version: 1 })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain('连接中断')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  const calls = vi.mocked(analyticsApi.writeCost).mock.calls
  expect(calls[0]![2]).toEqual(calls[1]![2])
  expect(calls[0]![2].content?.unit_cost).toBe('4.5')
  expect(wrapper.emitted('changed')).toHaveLength(1)
  expect(wrapper.emitted('working')).toEqual([[true], [false], [true], [false]])
})

it('shows historical evidence as text and blocks editing a changed source', async () => {
  vi.mocked(analyticsApi.costHistory).mockResolvedValue({
    ...history,
    source_current: false,
    version: 1,
    history: [
      {
        id: 3,
        version: 1,
        status: 'stale',
        action: 'upsert',
        unit_cost: '3.2500',
        currency: 'USD',
        evidence_ref: '<img src=x onerror=alert(1)>',
        evidence_at: '2026-10-06T00:00:00Z',
        recorded_at: '2026-10-07T00:00:00Z',
      },
    ],
  })
  const wrapper = mount(OrderCostEditor, {
    props: { shopId: 1, rowId: 9, timezone: 'Asia/Shanghai' },
  })
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('来源变化待重核')
  expect(wrapper.text()).toContain('<img src=x onerror=alert(1)>')
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.find('form').exists()).toBe(false)
})

it('ignores evidence arriving after switching shop', async () => {
  let release: (value: CostHistory) => void = () => undefined
  vi.mocked(analyticsApi.costHistory).mockReturnValue(
    new Promise((resolve) => {
      release = resolve
    }),
  )
  const wrapper = mount(OrderCostEditor, {
    props: { shopId: 1, rowId: 9, timezone: 'Asia/Shanghai' },
  })
  await wrapper.get('button').trigger('click')
  await wrapper.setProps({ shopId: 2, rowId: 10 })
  release(history)
  await flushPromises()
  expect(wrapper.find('section').exists()).toBe(false)
})

it('keeps a pending cost editor mounted until its write finishes, then permits historical paging', async () => {
  const result: AnalysisResult = {
    scope: {
      cost_mode: 'seller_history',
      start_at: '2026-10-07T00:00:00Z',
      end_at: '2026-10-08T00:00:00Z',
      timezone: 'UTC',
      currency: 'USD',
      data_identity: 'synthetic',
      intent: 'summary',
      min_quantity: 1,
      max_margin_percent: '20',
    },
    source_revision: 4,
    calculated_at: '2026-10-10T00:00:00Z',
    engine: 'local_rules',
    formula: '',
    cost_basis: '',
    fee_gaps: [],
    warnings: [],
    skus: [],
    ranking_available: false,
    answer: '',
    candidates: [],
    summary: {
      sku: null,
      line_count: 21,
      purchased_quantity: 21,
      sales: '21',
      cost: null,
      gross_profit: null,
      margin_percent: null,
      known_sales_subtotal: '21',
      sales_known_lines: 21,
      known_cost_subtotal: '0',
      cost_known_lines: 0,
      known_gross_subtotal: '0',
      gross_known_lines: 0,
    },
    lines: Array.from({ length: 21 }, (_, i) => ({
      order_id: `O${i + 1}`,
      line_id: '1',
      sku: 'SYN',
      status: 'paid',
      ordered_at: '2026-10-07T00:00:00Z',
      currency: 'USD',
      quantity: 1,
      included: true,
      unit_price: '1',
      discount: '0',
      refund: '0',
      sales: '1',
      cost: null,
      gross_profit: null,
      gaps: [],
      cost_source: null,
      source: {
        row_id: 9 + i,
        batch_id: 2,
        row_number: i + 2,
        filename: 'synthetic.csv',
        sheet_name: '',
        exported_at: null,
        imported_at: '2026-10-07T00:00:00Z',
        data_identity: 'synthetic',
      },
    })),
  }
  const wrapper = mount(AnalysisEvidence, { props: { shopId: 1, result, editCosts: true } })
  const editor = wrapper.findAllComponents(OrderCostEditor)[0]!
  await editor.get('button').trigger('click')
  await flushPromises()
  const fields = editor.findAll('input')
  await fields[0]!.setValue('3.25')
  await editor.get('select').setValue('USD')
  await fields[1]!.setValue('Synthetic receipt')
  await fields[2]!.setValue('2026-10-06T08:00:00+08:00')
  await editor.get('input[type="checkbox"]').setValue(true)
  let release: (value: CostHistory) => void = () => undefined
  vi.mocked(analyticsApi.writeCost).mockReturnValue(
    new Promise((resolve) => {
      release = resolve
    }),
  )
  await editor.get('form').trigger('submit')
  const next = wrapper.get('.pagination button:last-child')
  expect(next.attributes('disabled')).toBeDefined()
  await next.trigger('click')
  expect(wrapper.findAllComponents(OrderCostEditor)[0]!.props('rowId')).toBe(9)
  release({ ...history, version: 1 })
  await flushPromises()
  expect(wrapper.emitted('costsWorking')).toEqual([[true], [false]])
  expect(wrapper.emitted('costsChanged')).toHaveLength(1)
  await wrapper.setProps({ stale: true })
  expect(next.attributes('disabled')).toBeUndefined()
  await next.trigger('click')
  expect(wrapper.findAllComponents(OrderCostEditor)).toHaveLength(1)
  expect(wrapper.findComponent(OrderCostEditor).props('rowId')).toBe(29)
})
