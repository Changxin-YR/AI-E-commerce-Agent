import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import ScheduleEditor from '@/components/ScheduleEditor.vue'
import { rulesApi, type BusinessRule } from '@/api/businessRules'
import type { Shop } from '@/types/identity'

vi.mock('@/api/businessRules', () => ({ rulesApi: { current: vi.fn() } }))
const shop: Shop = {
  id: 1,
  code: 'synthetic',
  name: 'Synthetic',
  platform: 'other',
  market: 'US',
  currency: 'USD',
  timezone: 'Asia/Shanghai',
  connection_status: 'file_only',
}
const rule: BusinessRule = {
  version: 7,
  previous_version: 0,
  restored_from: null,
  shop_id: 1,
  channel: 'generic',
  data_identity: 'user_import',
  action: 'save',
  active: true,
  created_at: null,
  values: {
    max_age_hours: 12,
    min_quantity: 2,
    max_margin_percent: '10',
    advertising_daily_budget: null,
    currency: 'USD',
    notes: { target_site: '', warehouse: '', logistics: '', brand_voice: '', support_wording: '' },
    basis: 'Synthetic',
    automation: 'manual_only',
  },
}

it('ignores late operations rules after switching to a report and resets report consent', async () => {
  let release: (value: BusinessRule) => void = () => undefined
  vi.mocked(rulesApi.current).mockReturnValueOnce(
    new Promise((resolve) => {
      release = resolve
    }),
  )
  const wrapper = mount(ScheduleEditor, { props: { shop, busy: false } })
  await wrapper.get('#schedule-task').setValue('report')
  release(rule)
  await flushPromises()
  expect(wrapper.get<HTMLInputElement>('#schedule-age').element.value).toBe('24')
  expect(wrapper.get<HTMLInputElement>('#schedule-age').element.disabled).toBe(false)
  const confirm = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]').slice(-1)[0]!
  await confirm.setValue(true)
  await wrapper.get('#schedule-frequency').setValue('monthly')
  expect(confirm.element.checked).toBe(false)
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('save')).toBeUndefined()
  await confirm.setValue(true)
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('save')?.[0]?.[0]).toMatchObject({
    task: 'report',
    frequency: 'monthly',
    rule_revision_id: 0,
    weekday: 0,
    month_day: 1,
    report_currencies: [],
  })
})

it('reloads and binds operations rules when switching back from reporting', async () => {
  vi.mocked(rulesApi.current).mockResolvedValue(rule)
  const wrapper = mount(ScheduleEditor, { props: { shop, busy: false } })
  await flushPromises()
  await wrapper.get('#schedule-task').setValue('report')
  await wrapper.get('#schedule-age').setValue(50)
  await wrapper.get('#schedule-task').setValue('operations')
  await flushPromises()
  expect(wrapper.get<HTMLInputElement>('#schedule-age').element.value).toBe('12')
  expect(wrapper.get<HTMLInputElement>('#schedule-age').element.disabled).toBe(true)
  expect(wrapper.text()).toContain('绑定经营规则版本 #7')
})
