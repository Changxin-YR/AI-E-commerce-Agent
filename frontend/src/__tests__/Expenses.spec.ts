import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ExpenseEditor from '@/components/ExpenseEditor.vue'
import ExpenseEvidence from '@/components/ExpenseEvidence.vue'
import ExpensesView from '@/views/ExpensesView.vue'
import { expensesApi } from '@/api/expenses'
import { identityApi } from '@/api/identity'
import type { ExpenseSaved, ExpenseContent, ExpenseScope } from '@/types/expenses'

vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('@/api/identity', () => ({ identityApi: { shops: vi.fn() } }))
vi.mock('@/api/expenses', () => ({
  expensesApi: {
    get: vi.fn(),
    list: vi.fn(),
    write: vi.fn(),
    orders: vi.fn(),
    control: vi.fn(),
    summary: vi.fn(),
  },
}))
const scope: ExpenseScope = { data_identity: 'synthetic', channel: 'generic' }
const content: ExpenseContent = {
  label: '<img src=x onerror=alert(1)>',
  amount: '12.3456',
  currency: 'USD',
  category: 'shipping',
  occurred_at: '2026-10-07T00:30:00Z',
  timezone: 'UTC',
  evidence_ref: 'REF-1',
  evidence_note: 'private evidence',
  allocation: 'shop',
  order_line_id: null,
  expected_source_row_id: null,
  expected_source_revision: null,
  reason: 'source checked',
}
const fee: ExpenseSaved = {
  id: 5,
  shop_id: 1,
  ...scope,
  version: 1,
  status: 'active',
  created_at: '2026-10-09T00:00:00Z',
  snapshot: { content, source: null, order_id: null, line_id: null, sku: null, order_status: null },
  history: [],
}
const source = {
  batch_id: 1,
  row_id: 2,
  row_number: 2,
  filename: 'evidence.csv',
  sheet_name: '',
  exported_at: null,
  imported_at: '2026-10-09T00:00:00Z',
  data_identity: 'synthetic',
}
const available = {
  source_revision: 2,
  items: [
    { id: 1, order_id: 'O1', line_id: '1', sku: 'A', currency: 'USD', status: 'paid', source },
  ],
}
const wrappers: { unmount: () => void }[] = []
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(identityApi.shops).mockResolvedValue([
    {
      id: 1,
      code: 'test',
      name: 'Synthetic',
      platform: 'other',
      market: 'US',
      currency: 'USD',
      timezone: 'UTC',
      connection_status: 'file_only',
    },
  ])
  vi.mocked(expensesApi.list).mockResolvedValue({ items: [fee], next_cursor: null })
  vi.mocked(expensesApi.get).mockResolvedValue(fee)
  vi.mocked(expensesApi.orders).mockResolvedValue(available)
})
afterEach(() => wrappers.splice(0).forEach((w) => w.unmount()))
async function view() {
  const wrapper = mount(ExpensesView, {
    global: { stubs: { RouterLink: true, SupportSource: true } },
  })
  wrappers.push(wrapper)
  await flushPromises()
  return wrapper
}
function editor() {
  const wrapper = mount(ExpenseEditor, {
    props: { shopId: 1, scope, existing: fee },
    global: { stubs: { SupportSource: true } },
  })
  wrappers.push(wrapper)
  return wrapper
}
it('renders evidence as text and shows explicit currency, time and allocation', () => {
  const wrapper = mount(ExpenseEvidence, { props: { shopId: 1, snapshot: fee.snapshot! } })
  wrappers.push(wrapper)
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.text()).toContain(content.label)
  expect(wrapper.text()).toContain('USD 12.3456')
  expect(wrapper.text()).toContain('(UTC)')
  expect(wrapper.text()).toContain('未分摊')
})
it('resets confirmation on amount edits and binds current order source', async () => {
  const wrapper = editor()
  await wrapper.get('input[type=checkbox]').setValue(true)
  await wrapper.get('#fee-amount').setValue('13.0001')
  expect((wrapper.get('input[type=checkbox]').element as HTMLInputElement).checked).toBe(false)
  await wrapper.get('#fee-allocation').setValue('order_line')
  await wrapper.get('#fee-order').setValue('O1')
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '查找当前订单行')!
    .trigger('click')
  await flushPromises()
  await wrapper.get('#fee-line').setValue('1')
  await wrapper.get('input[type=checkbox]').setValue(true)
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('save')?.[0]?.[0]).toMatchObject({
    amount: '13.0001',
    order_line_id: 1,
    expected_source_row_id: 2,
    expected_source_revision: 2,
  })
})
it('drops late order lookup after query changes', async () => {
  let resolve!: (value: typeof available) => void
  vi.mocked(expensesApi.orders).mockReturnValue(
    new Promise((r) => {
      resolve = r
    }),
  )
  const wrapper = editor()
  await wrapper.get('#fee-allocation').setValue('order_line')
  await wrapper.get('#fee-order').setValue('O1')
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '查找当前订单行')!
    .trigger('click')
  await wrapper.get('#fee-order').setValue('O2')
  resolve(available)
  await flushPromises()
  expect(wrapper.find('#fee-line').exists()).toBe(false)
})
it('drops late history responses when identity changes', async () => {
  let resolve!: (value: { items: ExpenseSaved[]; next_cursor: null }) => void
  vi.mocked(expensesApi.list).mockReturnValueOnce(
    new Promise((r) => {
      resolve = r
    }),
  )
  const wrapper = await view()
  await wrapper.get('#expense-identity').setValue('synthetic')
  resolve({ items: [fee], next_cursor: null })
  await flushPromises()
  expect(wrapper.text()).not.toContain(content.label)
})
it('hides old evidence on failed refresh and restores saved scope', async () => {
  const wrapper = await view()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '查看费用 #5')!
    .trigger('click')
  await flushPromises()
  expect((wrapper.get('#expense-identity').element as HTMLSelectElement).value).toBe('synthetic')
  expect(wrapper.text()).toContain('private evidence')
  vi.mocked(expensesApi.get).mockRejectedValueOnce(new Error('read failed'))
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '刷新费用')!
    .trigger('click')
  await flushPromises()
  expect(wrapper.text()).not.toContain('private evidence')
})
it('retries unknown saves with the exact original UUID and payload', async () => {
  const wrapper = await view()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '新增实际费用')!
    .trigger('click')
  vi.mocked(expensesApi.write).mockRejectedValueOnce(new Error('network unknown'))
  wrapper.getComponent(ExpenseEditor).vm.$emit('save', { ...content })
  await flushPromises()
  const original = vi.mocked(expensesApi.write).mock.calls[0]
  expect(wrapper.text()).not.toContain('private evidence')
  vi.mocked(expensesApi.write).mockResolvedValueOnce(fee)
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '回查原保存请求')!
    .trigger('click')
  await flushPromises()
  expect(vi.mocked(expensesApi.write).mock.calls[1]).toEqual(original)
  expect(wrapper.text()).toContain('private evidence')
})

it('keeps unsaved fee inputs while reading a summary', async () => {
  const wrapper = await view()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '新增实际费用')!
    .trigger('click')
  await wrapper.get('#fee-label').setValue('unsaved fee')
  let finish!: () => void
  vi.mocked(expensesApi.summary).mockReturnValue(
    new Promise((_, reject) => {
      finish = () => reject(new Error('summary unavailable'))
    }),
  )
  await wrapper
    .findAll('form')
    .find((form) => form.find('#expense-start').exists())!
    .trigger('submit')
  await flushPromises()
  expect((wrapper.get('#fee-label').element as HTMLInputElement).value).toBe('unsaved fee')
  finish()
  await flushPromises()
  expect((wrapper.get('#fee-label').element as HTMLInputElement).value).toBe('unsaved fee')
})
