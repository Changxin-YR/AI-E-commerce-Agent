import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import AppliedRules from '@/components/AppliedRules.vue'
import { rulesApi, type BusinessRule } from '@/api/businessRules'
import type { OperationScope } from '@/types/operations'

vi.mock('@/api/businessRules', () => ({ rulesApi: { current: vi.fn() } }))
const scope: OperationScope = {
  start_at: '2026-10-01T00:00:00Z',
  end_at: '2026-10-02T00:00:00Z',
  timezone: 'UTC',
  currency: 'USD',
  data_identity: 'synthetic',
  intent: 'low_margin',
  channel: 'generic',
  max_age_hours: 24,
  min_quantity: 1,
  max_margin_percent: '20',
}

it('ignores a delayed rule response from a previous shop and blocks loading errors', async () => {
  let release: (rule: BusinessRule) => void = () => undefined
  const delayed = new Promise<BusinessRule>((resolve) => {
    release = resolve
  })
  vi.mocked(rulesApi.current)
    .mockReturnValueOnce(delayed)
    .mockRejectedValueOnce(new Error('failed'))
  const wrapper = mount(AppliedRules, {
    props: { shop: 1, scope },
    global: { stubs: { RouterLink: true } },
  })
  await wrapper.setProps({ shop: 2 })
  await flushPromises()
  release({ shop_id: 1, version: 99 } as BusinessRule)
  await flushPromises()
  expect(wrapper.emitted('loaded')).toBeUndefined()
  expect(wrapper.emitted('pending')?.every((event) => event[0] === true)).toBe(true)
  expect(wrapper.text()).not.toContain('#99')
})
