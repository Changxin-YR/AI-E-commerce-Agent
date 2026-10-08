import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import OutboundMailReview from '@/components/OutboundMailReview.vue'
import { outboundApi } from '@/api/outbound'
import type { OutboundMail } from '@/types/outbound'
vi.mock('@/api/outbound', () => ({
  outboundApi: { approve: vi.fn(), send: vi.fn(), reconcile: vi.fn() },
}))
const mail: OutboundMail = {
  id: 1,
  shop_id: 1,
  channel_id: 1,
  run_id: 9,
  sender: 'owner@example.invalid',
  recipient: 'test@example.invalid',
  subject: 'Synthetic',
  body: '<script>alert(1)</script>',
  content_hash: 'hash',
  status: 'draft',
  source_status: 'current',
  channel_status: 'active',
  version: 1,
  risk: 'R2',
  max_submissions: 1,
  dispatch_at: null,
  receipt_id: null,
  provider_event: '',
  checked_at: null,
  received_at: null,
  receipt_evidence: null,
  created_at: '2026-10-09T00:00:00Z',
  approvals: [],
}
it('requires consent, resets it on changed bounds and renders source text safely', async () => {
  const wrapper = mount(OutboundMailReview, { props: { mail, timezone: 'Asia/Shanghai' } })
  const approve = () => wrapper.findAll('button').find((b) => b.text() === '单次批准并提交')!
  expect(approve().attributes('disabled')).toBeDefined()
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.text()).toContain('<script>alert(1)</script>')
  await wrapper.get('input[type=checkbox]').setValue(true)
  expect(approve().attributes('disabled')).toBeUndefined()
  await wrapper.get('input[type=number]').setValue(2)
  expect(approve().attributes('disabled')).toBeDefined()
  await wrapper.setProps({ mail: { ...mail, source_status: 'stale', version: 2 } })
  expect(wrapper.text()).not.toContain('单次批准并提交')
})
it('unknown state exposes only reconciliation and never starts a send on mount', async () => {
  vi.mocked(outboundApi.send).mockClear()
  const wrapper = mount(OutboundMailReview, {
    props: { mail: { ...mail, status: 'unknown', dispatch_at: mail.created_at }, timezone: 'UTC' },
  })
  await flushPromises()
  expect(wrapper.text()).toContain('结果未知，请回查')
  expect(wrapper.text()).not.toContain('单次批准并提交')
  expect(outboundApi.send).not.toHaveBeenCalled()
})
