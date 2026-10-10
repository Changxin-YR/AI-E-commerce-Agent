import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import SettlementRecords from '@/components/SettlementRecords.vue'
import { settlementsApi as api } from '@/api/settlements'
import type { SettlementPreview, SettlementSaved } from '@/types/settlements'
vi.mock('@/api/settlements', () => ({
  settlementsApi: {
    list: vi.fn(),
    get: vi.fn(),
    preview: vi.fn(),
    write: vi.fn(),
    control: vi.fn(),
    current: vi.fn(),
  },
}))
const scope = {
  data_identity: 'synthetic' as const,
  channel: 'generic' as const,
  start_at: '2026-10-07T00:00:00Z',
  end_at: '2026-10-08T00:00:00Z',
  timezone: 'UTC',
}
const content = {
  statement_id: 'S1',
  note: '<img src=x onerror=alert(1)> 合成周期',
  receipts: [
    {
      payout_ref: 'P1',
      receipt_ref: 'R1',
      amount: '80',
      currency: 'USD',
      received_at: '2026-10-08T01:00:00Z',
      timezone: 'UTC',
      note: '合成凭据说明',
    },
  ],
}
const preview: SettlementPreview = {
  preview_hash: 'a'.repeat(64),
  snapshot: {
    scope,
    content,
    calculated_at: '2026-10-09T00:00:00Z',
    source_revision: 3,
    statements: [],
    totals: [],
    comparisons: [
      {
        payout_ref: 'P1',
        status: 'receipt_only',
        statement_ids: [],
        receipt_indexes: [0],
        difference: null,
      },
    ],
    outside_cycle_ids: [],
    coverage_status: 'unknown',
    balance_status: 'unknown',
    bank_status: 'unverified',
    checks: [],
  },
}
const saved: SettlementSaved = {
  id: 2,
  shop_id: 1,
  data_identity: 'synthetic',
  channel: 'generic',
  status: 'active',
  version: 1,
  content_version: 1,
  created_at: '2026-10-09T00:00:00Z',
  snapshot: preview.snapshot,
  history: [
    { version: 1, action: 'create', has_content: true, created_at: '2026-10-09T00:00:00Z' },
  ],
}
const wrappers: { unmount: () => void }[] = []
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.list).mockResolvedValue({ items: [saved], next_cursor: null })
  vi.mocked(api.get).mockResolvedValue(saved)
  vi.mocked(api.preview).mockResolvedValue(preview)
  vi.mocked(api.write).mockResolvedValue(saved)
  vi.mocked(api.current).mockResolvedValue({ record: saved, preview })
})
afterEach(() => wrappers.splice(0).forEach((w) => w.unmount()))
function setup(initialId?: number) {
  const w = mount(SettlementRecords, {
    props: { shopId: 1, scope, disabled: false, initialId },
    global: { stubs: { RouterLink: true, StatementEvidence: true } },
  })
  wrappers.push(w)
  return w
}
type Wrapper = ReturnType<typeof setup>
async function click(w: Wrapper, name: string) {
  const b = w.findAll('button').find((b) => b.text() === name)
  expect(b).toBeTruthy()
  await b!.trigger('click')
  await flushPromises()
}
async function edit(w: Wrapper) {
  await click(w, '新建结算登记')
  await w.get('#settlement-statement').setValue('S1')
  await w.get('#settlement-note').setValue(content.note)
  await w.get('form').trigger('submit')
  await flushPromises()
}
it('escapes source text and invalidates confirmation after cycle or receipt changes', async () => {
  const w = setup()
  await edit(w)
  expect(w.find('img').exists()).toBe(false)
  expect(w.text()).toContain(content.note)
  expect(w.text()).toContain('银行证据未核验')
  await w.get('input[type=checkbox]').setValue(true)
  await w.findAll('input[type=datetime-local]')[1]!.setValue('2026-10-09T00:00:00')
  expect(w.find('[aria-label="结算预览"]').exists()).toBe(false)
  await click(w, '添加人工到账凭据')
  await w.get('#receipt-amount-0').setValue('123.4567')
  await w.get('form').trigger('submit')
  await flushPromises()
  expect(
    vi.mocked(api.preview).mock.calls[vi.mocked(api.preview).mock.calls.length - 1]![1].content
      .receipts[0]!.amount,
  ).toBe('123.4567')
  await w.get('#receipt-ref-0').setValue('changed')
  expect(w.find('[aria-label="结算预览"]').exists()).toBe(false)
  expect(api.write).not.toHaveBeenCalled()
})
it('replays the exact unknown write and hides obsolete evidence', async () => {
  const w = setup()
  await edit(w)
  await w.get('input[type=checkbox]').setValue(true)
  vi.mocked(api.write).mockRejectedValueOnce(new Error('network'))
  await click(w, '保存结算登记')
  const request = vi.mocked(api.write).mock.calls[0]![1]
  expect(w.find('[aria-label="结算预览"]').exists()).toBe(false)
  expect(w.find('[role=alert]').exists()).toBe(true)
  await click(w, '回查原登记保存请求')
  expect(vi.mocked(api.write).mock.calls[1]![1]).toEqual(request)
  expect(w.text()).toContain('登记依据未变 · 版本 1')
})
it('drops late previews on focus and clears pending writes on scope change', async () => {
  const w = setup()
  let resolve!: (p: SettlementPreview) => void
  vi.mocked(api.preview).mockReturnValue(
    new Promise((r) => {
      resolve = r
    }),
  )
  await edit(w)
  window.dispatchEvent(new Event('focus'))
  resolve(preview)
  await flushPromises()
  expect(w.find('[aria-label="结算预览"]').exists()).toBe(false)
  vi.mocked(api.preview).mockResolvedValue(preview)
  await edit(w)
  await w.get('input[type=checkbox]').setValue(true)
  vi.mocked(api.write).mockRejectedValueOnce(new Error('network'))
  await click(w, '保存结算登记')
  await w.setProps({ shopId: 9 })
  expect(w.text()).not.toContain('回查原登记保存请求')
})
it('hides old detail on failed refresh and reports the error', async () => {
  const w = setup(2)
  await flushPromises()
  expect(w.text()).toContain(content.note)
  vi.mocked(api.current).mockRejectedValueOnce(new Error('read failed'))
  await click(w, '回读当前账单与凭据')
  expect(w.text()).not.toContain(content.note)
  expect(w.text()).toContain('read failed')
  vi.mocked(api.list).mockRejectedValueOnce(new Error('list failed'))
  await click(w, '读取结算登记')
  expect(w.text()).toContain('list failed')
})
it('uses saved cycle and latest version after atomic current read', async () => {
  const w = setup(2)
  await flushPromises()
  vi.mocked(api.current).mockResolvedValue({
    record: { ...saved, status: 'stale', version: 2 },
    preview,
  })
  await click(w, '回读当前账单与凭据')
  expect(w.text()).toContain('来源已变化 · 待重核')
  expect(api.write).not.toHaveBeenCalled()
  expect(api.get).toHaveBeenCalledTimes(1)
  await click(w, '修订并重新核对')
  await w.get('form').trigger('submit')
  await flushPromises()
  expect(vi.mocked(api.preview).mock.calls[0]![1]).toEqual({
    scope,
    settlement_id: 2,
    version: 2,
    content,
  })
})
it('clears historical body when the source is cleared during current read', async () => {
  const w = setup(2)
  await flushPromises()
  vi.mocked(api.current).mockResolvedValue({
    record: { ...saved, status: 'cleared', snapshot: null, history: [] },
    preview: null,
  })
  await click(w, '回读当前账单与凭据')
  expect(w.text()).toContain('正文及全部历史依据已清除')
  expect(w.text()).not.toContain(content.note)
  expect(w.find('[aria-label="结算当前依据"]').exists()).toBe(false)
})
it('resets consent on control changes and clears all visible data after clear', async () => {
  const w = setup(2)
  await flushPromises()
  await w.get('input[type=checkbox]').setValue(true)
  await w.get('#settlement-control').setValue('clear')
  expect((w.get('input[type=checkbox]').element as HTMLInputElement).checked).toBe(false)
  await w.get('input[type=checkbox]').setValue(true)
  vi.mocked(api.control).mockResolvedValue({
    ...saved,
    status: 'cleared',
    snapshot: null,
    history: [],
  })
  await click(w, '确认处理登记')
  expect(w.text()).not.toContain(content.note)
})
