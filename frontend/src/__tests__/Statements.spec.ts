import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import StatementsView from '@/views/StatementsView.vue'
import StatementResult from '@/components/StatementResult.vue'
import StatementEvidence from '@/components/StatementEvidence.vue'
import SupportSource from '@/components/SupportSource.vue'
import { statementsApi } from '@/api/statements'
import { identityApi } from '@/api/identity'
import { analyticsApi } from '@/api/analytics'
import type { StatementReconciliation } from '@/types/statements'

vi.mock('vue-router', () => ({ useRoute: () => ({ query: { shop: '1' } }) }))
vi.mock('@/api/identity', () => ({ identityApi: { shops: vi.fn() } }))
vi.mock('@/api/statements', () => ({ statementsApi: { reconcile: vi.fn() } }))
vi.mock('@/api/analytics', () => ({ analyticsApi: { source: vi.fn() } }))
const source = {
  batch_id: 3,
  row_id: 4,
  row_number: 2,
  filename: 'bill.csv',
  sheet_name: '',
  exported_at: null,
  imported_at: '2026-10-09T00:00:00Z',
  data_identity: 'synthetic',
}
const result: StatementReconciliation = {
  scope: {
    data_identity: 'synthetic',
    channel: 'generic',
    timezone: 'UTC',
    start_at: '2026-10-07T00:00:00Z',
    end_at: '2026-10-08T00:00:00Z',
  },
  source_revision: 3,
  calculated_at: '2026-10-09T00:00:00Z',
  statements: [
    {
      id: 1,
      statement_id: 'S1',
      line_id: '1',
      entry_type: 'fee',
      amount: '12.3456',
      currency: 'USD',
      occurred_at: '2026-10-07T08:00:00Z',
      evidence_ref: 'REF-1',
      fee_name: '<img src=x onerror=alert(1)>',
      settlement_id: '',
      order_id: '',
      note: 'private bill evidence',
      source,
    },
  ],
  totals: [{ currency: 'USD', entry_type: 'fee', amount: '12.3456', count: 1 }],
  comparisons: [
    {
      evidence_ref: 'REF-1',
      status: 'matched',
      statement_ids: [1],
      expenses: [
        {
          id: 2,
          version: 3,
          label: 'Fee',
          category: 'platform',
          allocation: 'shop',
          evidence_ref: 'REF-1',
          amount: '12.3456',
          currency: 'USD',
          occurred_at: '2026-10-07T08:00:00Z',
        },
      ],
      difference: '0.0000',
    },
  ],
  stale_expenses: 0,
  withdrawn_expenses: 0,
  checks: ['费用完整性未知'],
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
  vi.mocked(statementsApi.reconcile).mockResolvedValue(result)
})
afterEach(() => wrappers.splice(0).forEach((w) => w.unmount()))
async function view() {
  const wrapper = mount(StatementsView, {
    global: { stubs: { RouterLink: true, SupportSource: true } },
  })
  wrappers.push(wrapper)
  await flushPromises()
  return wrapper
}
it('hides previous results before failed refresh', async () => {
  const wrapper = await view()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain('private bill evidence')
  vi.mocked(statementsApi.reconcile).mockRejectedValueOnce(new Error('network failed'))
  await wrapper.get('form').trigger('submit')
  expect(wrapper.text()).not.toContain('private bill evidence')
  await flushPromises()
  expect(wrapper.text()).toContain('network failed')
})
it('drops a late response when scope changes', async () => {
  let resolve!: (value: StatementReconciliation) => void
  vi.mocked(statementsApi.reconcile).mockReturnValue(
    new Promise((r) => {
      resolve = r
    }),
  )
  const wrapper = await view()
  await wrapper.get('form').trigger('submit')
  await wrapper.get('#statement-identity').setValue('synthetic')
  resolve(result)
  await flushPromises()
  expect(wrapper.findComponent(StatementResult).exists()).toBe(false)
})
it('invalidates both existing and in-flight data on returning to the window', async () => {
  const wrapper = await view()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  window.dispatchEvent(new Event('focus'))
  await flushPromises()
  expect(wrapper.findComponent(StatementResult).exists()).toBe(false)
  let resolve!: (value: StatementReconciliation) => void
  vi.mocked(statementsApi.reconcile).mockReturnValue(
    new Promise((r) => {
      resolve = r
    }),
  )
  await wrapper.get('form').trigger('submit')
  window.dispatchEvent(new Event('focus'))
  resolve(result)
  await flushPromises()
  expect(wrapper.findComponent(StatementResult).exists()).toBe(false)
})
it('filters comparisons and keeps zero differences visible', async () => {
  const wrapper = mount(StatementResult, {
    props: { result, shopId: 1 },
    global: { stubs: { RouterLink: true, SupportSource: true } },
  })
  wrappers.push(wrapper)
  expect(wrapper.text()).toContain('差额 USD 0.0000')
  await wrapper.get('#statement-filter').setValue('amount_difference')
  expect(wrapper.findAll('article')).toHaveLength(0)
  expect(wrapper.text()).toContain('当前筛选无费用核对条目')
})
it('escapes statement source markup and identifies payout uncertainty', () => {
  const wrapper = mount(StatementEvidence, {
    props: { line: { ...result.statements[0]!, entry_type: 'payout' }, shopId: 1, timezone: 'UTC' },
    global: { stubs: { RouterLink: true, SupportSource: true } },
  })
  wrappers.push(wrapper)
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.text()).toContain('<img src=x onerror=alert(1)>')
  expect(wrapper.text()).toContain('平台记载回款 · 到账待核')
  expect(wrapper.text()).toContain('(UTC)')
})
it('clears a previously expanded raw source before a failed reread', async () => {
  vi.mocked(analyticsApi.source).mockResolvedValue({
    reference: source,
    batch_status: 'committed',
    raw: { note: 'private raw' },
    corrections: {},
    normalized: {},
  })
  const wrapper = mount(SupportSource, { props: { source, shopId: 1 } })
  wrappers.push(wrapper)
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('private raw')
  vi.mocked(analyticsApi.source).mockRejectedValueOnce(new Error('cleared'))
  await wrapper.get('button').trigger('click')
  expect(wrapper.text()).not.toContain('private raw')
  await flushPromises()
  expect(wrapper.text()).toContain('cleared')
})

it('preserves loaded raw data across a parent refresh of the same source identity', async () => {
  vi.mocked(analyticsApi.source).mockResolvedValue({
    reference: source,
    batch_status: 'committed',
    raw: { note: 'loaded raw' },
    corrections: {},
    normalized: {},
  })
  const wrapper = mount(SupportSource, { props: { source, shopId: 1 } })
  wrappers.push(wrapper)
  await wrapper.get('button').trigger('click')
  await flushPromises()
  await wrapper.setProps({ source: { ...source } })
  expect(wrapper.text()).toContain('loaded raw')
  await wrapper.setProps({ source: { ...source, row_id: 7 } })
  expect(wrapper.text()).not.toContain('loaded raw')
})

it('drops a late raw-source response after switching away and back', async () => {
  let resolve!: (value: Awaited<ReturnType<typeof analyticsApi.source>>) => void
  vi.mocked(analyticsApi.source).mockReturnValue(
    new Promise((r) => {
      resolve = r
    }),
  )
  const wrapper = mount(SupportSource, { props: { source, shopId: 1 } })
  wrappers.push(wrapper)
  await wrapper.get('button').trigger('click')
  await wrapper.setProps({ source: { ...source, row_id: 7 } })
  await wrapper.setProps({ source: { ...source } })
  resolve({
    reference: source,
    batch_status: 'committed',
    raw: { note: 'late raw' },
    corrections: {},
    normalized: {},
  })
  await flushPromises()
  expect(wrapper.text()).not.toContain('late raw')
})
