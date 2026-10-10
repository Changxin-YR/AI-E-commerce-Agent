import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SupportDelivery from '@/components/SupportDelivery.vue'
import { supportApi } from '@/api/support'
import type { ReplyDraft } from '@/types/support'

vi.mock('@/api/support', () => ({
  supportApi: {
    review: vi.fn(),
    delivery: vi.fn(),
    recordManualAction: vi.fn(),
    manualActions: vi.fn(),
  },
}))
afterEach(() => vi.resetAllMocks())
const item: ReplyDraft = {
  id: 1,
  version: 2,
  source_status: 'current',
  status: 'human_review',
  engine: 'local_rules',
  created_at: '2026-10-10T01:00:00Z',
  updated_at: '2026-10-10T01:00:00Z',
  external_status: 'not_submitted',
  reviewed_version: 2,
  reviewed_at: '2026-10-10T01:00:00Z',
  reviewed_language: 'en',
  snapshot: {
    message: {
      id: 1,
      message_id: 'M1',
      body: 'Please refund',
      order_id: '',
      language: 'en',
      channel: 'generic',
      sent_at: '2026-10-09T01:00:00Z',
      source: {
        batch_id: 1,
        row_id: 1,
        row_number: 2,
        filename: 'synthetic.csv',
        sheet_name: '',
        imported_at: '2026-10-10T01:00:00Z',
        exported_at: null,
        data_identity: 'synthetic',
      },
    },
    orders: [],
    order_verified: false,
    policies: [],
    intents: ['refund'],
    reasons: ['需核验'],
    handoff_summary: '需核验',
    reply: 'No refund confirmed.',
  },
}
function setup(value = item) {
  return mount(SupportDelivery, {
    props: { item: value, shopId: 1, timezone: 'Asia/Shanghai', disabled: false },
  })
}
describe('Support delivery', () => {
  it('binds explicit review to the current version and selected language', async () => {
    const wrapper = setup({ ...item, reviewed_version: null, reviewed_at: null })
    const copy = wrapper.findAll('button').find((b) => b.text() === '复制通用草稿')!
    expect(copy.attributes('disabled')).toBeDefined()
    const confirm = wrapper.findAll('button').find((b) => b.text() === '确认当前版本已审阅')!
    expect(confirm.attributes('disabled')).toBeDefined()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    vi.mocked(supportApi.review).mockResolvedValue(item)
    await confirm.trigger('click')
    await flushPromises()
    expect(supportApi.review).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ id: 1, version: 2 }),
      'en',
    )
    expect(wrapper.emitted('updated')).toEqual([[item]])
    await wrapper.setProps({ item })
    expect(copy.attributes('disabled')).toBeUndefined()
    await wrapper.setProps({ item: { ...item, version: 3 } })
    expect(copy.attributes('disabled')).toBeDefined()
  })
  it('clears confirmation when evidence changes and reuses UUID after an unknown response', async () => {
    const wrapper = setup()
    const form = wrapper.get('form')
    const fields = form.findAll('input:not([type="checkbox"])')
    await fields[0]!.setValue('2026-10-09T18:00:00+08:00')
    await fields[1]!.setValue('原平台人工回复')
    await fields[2]!.setValue('SYN-EVIDENCE')
    const confirmed = form.get('input[type="checkbox"]')
    await confirmed.setValue(true)
    await fields[2]!.setValue('SYN-EVIDENCE-2')
    expect((confirmed.element as HTMLInputElement).checked).toBe(false)
    await confirmed.setValue(true)
    vi.mocked(supportApi.recordManualAction)
      .mockRejectedValueOnce(new Error('unknown'))
      .mockResolvedValueOnce({
        id: 1,
        draft_id: 1,
        draft_version: 2,
        occurred_at: '2026-10-09T10:00:00Z',
        recorded_at: '2026-10-10T01:00:00Z',
        details: { method: '原平台人工回复', evidence_ref: 'SYN-EVIDENCE-2', note: '' },
        provenance: 'seller_reported',
        external_status: 'not_submitted',
      })
    await form.trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('unknown')
    await form.trigger('submit')
    await flushPromises()
    const calls = vi.mocked(supportApi.recordManualAction).mock.calls
    expect(calls[0]![2].request_id).toBe(calls[1]![2].request_id)
    expect(wrapper.text()).toContain('人工操作自报已登记')
    expect(wrapper.text()).toContain('SYN-EVIDENCE-2')
    expect(wrapper.text()).toContain('系统外部未提交')
    const events = wrapper.emitted('dirty')!
    expect(events[events.length - 1]).toEqual([false])
  })
  it('discards late review responses after changing object', async () => {
    let resolve!: (result: ReplyDraft) => void
    vi.mocked(supportApi.review).mockImplementation(
      () =>
        new Promise((r) => {
          resolve = r
        }),
    )
    const wrapper = setup({ ...item, reviewed_at: null, reviewed_version: null })
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '确认当前版本已审阅')!
      .trigger('click')
    await wrapper.setProps({ item: { ...item, id: 9 } })
    resolve(item)
    await flushPromises()
    expect(wrapper.emitted('updated')).toBeUndefined()
    expect(wrapper.text()).not.toContain('SYN-EVIDENCE')
  })
})
