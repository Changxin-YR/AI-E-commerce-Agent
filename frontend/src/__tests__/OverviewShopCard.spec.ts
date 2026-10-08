import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import OverviewShopCard from '@/components/OverviewShopCard.vue'
import { analyticsApi } from '@/api/analytics'
import type { SourceDetail } from '@/types/analytics'
import type { ShopOverview } from '@/types/overview'

vi.mock('@/api/analytics', () => ({ analyticsApi: { source: vi.fn() } }))
const shop: ShopOverview = {
  shop_id: 1,
  shop_name: 'Synthetic',
  platform: 'other',
  market: 'US',
  source_revision: 1,
  currencies: [],
  inventory: [],
  inventory_low: null,
  inventory_unknown: 0,
  messages: [],
  message_count: null,
  tasks: [],
  tasks_has_more: false,
  sources: [
    {
      row_id: 1,
      batch_id: 1,
      row_number: 1,
      filename: 'source.csv',
      sheet_name: '',
      exported_at: null,
      imported_at: '2026-10-07T00:00:00Z',
      data_identity: 'synthetic',
    },
  ],
}

it('keeps missing export and stock coverage unknown, and ignores delayed old evidence', async () => {
  let finish: (detail: SourceDetail) => void = () => undefined
  vi.mocked(analyticsApi.source).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const wrapper = mount(OverviewShopCard, {
    props: { shop, timezone: 'Asia/Shanghai' },
    global: { stubs: { RouterLink: true } },
  })
  expect(wrapper.text()).toContain('含导出时间未知的来源')
  expect(wrapper.text()).toContain('已知低库存 未知')
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '查看原始行 #1')!
    .trigger('click')
  await wrapper.setProps({ shop: { ...shop, shop_id: 2, shop_name: 'Next', sources: [] } })
  finish({
    reference: shop.sources[0]!,
    batch_status: 'committed',
    raw: { message: 'OLD SECRET' },
    normalized: {},
    corrections: {},
  })
  await flushPromises()
  expect(wrapper.text()).not.toContain('OLD SECRET')
  expect(wrapper.text()).toContain('未获取来源')
  wrapper.unmount()
})

it('does not attach an old source error to a new report', async () => {
  let fail: (error: Error) => void = () => undefined
  vi.mocked(analyticsApi.source).mockReturnValueOnce(
    new Promise((_, reject) => {
      fail = reject
    }),
  )
  const wrapper = mount(OverviewShopCard, {
    props: { shop, timezone: 'Asia/Shanghai' },
    global: { stubs: { RouterLink: true } },
  })
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '查看原始行 #1')!
    .trigger('click')
  await wrapper.setProps({ shop: { ...shop, source_revision: 2 } })
  fail(new Error('old source failure'))
  await flushPromises()
  expect(wrapper.text()).not.toContain('old source failure')
  wrapper.unmount()
})
