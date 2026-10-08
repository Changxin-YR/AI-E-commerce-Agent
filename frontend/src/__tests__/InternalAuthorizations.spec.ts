import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import InternalAuthorizations from '@/components/InternalAuthorizations.vue'
import { authorizationsApi, type InternalAuthorization } from '@/api/authorizations'
import type { AgentRun } from '@/types/agent'

vi.mock('@/api/authorizations', () => ({
  authorizationsApi: { list: vi.fn(), create: vi.fn(), revoke: vi.fn(), revert: vi.fn() },
  authorizationLabels: { active: '有效' },
}))

it('ignores a delayed response from the previous shop', async () => {
  let release: (data: { items: InternalAuthorization[]; next_before_id: null }) => void = () =>
    undefined
  vi.mocked(authorizationsApi.list)
    .mockReturnValueOnce(
      new Promise((resolve) => {
        release = resolve
      }),
    )
    .mockResolvedValueOnce({ items: [], next_before_id: null })
  const wrapper = mount(InternalAuthorizations, { props: { shop: 1, run: null, busy: false } })
  await wrapper.setProps({ shop: 2 })
  await flushPromises()
  release({ items: [{ id: 99, shop_id: 1 } as InternalAuthorization], next_before_id: null })
  await flushPromises()
  expect(wrapper.text()).not.toContain('#99')
})

it('requires renewed consent when limits change and blocks stale creation', async () => {
  vi.mocked(authorizationsApi.list).mockResolvedValue({ items: [], next_before_id: null })
  const run: AgentRun = {
    id: 4,
    shop_id: 1,
    version: 1,
    status: 'waiting_approval',
    next_node: 'propose_tasks',
    source_status: 'current',
    template: 'daily',
    reason: 'findings_found',
    source_revision: 1,
    steps_used: 1,
    elapsed_ms: 1,
    steps: [],
    spent_usd: '0',
    reserved_usd: '0',
    model_status: 'not_used',
    created_at: '2026-10-01T00:00:00Z',
    external_status: 'not_submitted',
    budget: { max_steps: 12, max_seconds: 120, max_cost_usd: '0' },
    result: { findings: [{}] },
    input: {
      request_id: 'synthetic',
      template: 'daily',
      goal: '',
      product_id: null,
      message_id: null,
      allow_model: false,
      budget: { max_steps: 12, max_seconds: 120, max_cost_usd: '0' },
      scope: {
        data_identity: 'synthetic',
        intent: 'low_margin',
        channel: 'generic',
        max_age_hours: 24,
        min_quantity: 1,
        max_margin_percent: '20',
        start_at: '2026-10-01T00:00:00Z',
        end_at: '2026-10-02T00:00:00Z',
        timezone: 'UTC',
        currency: 'USD',
      },
    },
  }
  const wrapper = mount(InternalAuthorizations, { props: { shop: 1, run, busy: false } })
  await flushPromises()
  const save = () => wrapper.findAll('button').find((b) => b.text() === '保存预授权')!
  expect(save().attributes('disabled')).toBeDefined()
  await wrapper.get('input[type=checkbox]').setValue(true)
  expect(save().attributes('disabled')).toBeUndefined()
  await wrapper.get('input[type=number]').setValue(3)
  expect(save().attributes('disabled')).toBeDefined()
  await wrapper.setProps({ run: { ...run, source_status: 'stale' } })
  expect(wrapper.find('form').exists()).toBe(false)
})
