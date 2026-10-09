import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ProductEditReview from '@/components/ProductEditReview.vue'
import ProductEditsView from '@/views/ProductEditsView.vue'
import { identityApi } from '@/api/identity'
import { productQualityApi } from '@/api/productQuality'
import { productEditsApi } from '@/api/productEdits'
import { analyticsApi } from '@/api/analytics'
import type { EditSaved } from '@/types/productEdits'
import type { QualityResult } from '@/types/productQuality'

vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('@/api/identity', () => ({ identityApi: { shops: vi.fn() } }))
vi.mock('@/api/analytics', () => ({ analyticsApi: { revision: vi.fn() } }))
vi.mock('@/api/productQuality', () => ({ productQualityApi: { preview: vi.fn() } }))
vi.mock('@/api/productEdits', () => ({
  productEditsApi: { create: vi.fn(), get: vi.fn(), list: vi.fn(), decide: vi.fn() },
}))
const source = {
  batch_id: 1,
  row_id: 2,
  row_number: 2,
  filename: 'synthetic.csv',
  sheet_name: '',
  exported_at: null,
  imported_at: '2026-10-09T00:00:00Z',
  data_identity: 'synthetic',
}
const product = {
  sku: 'A',
  name: '<img src=x onerror=alert(1)>',
  facts: 'Steel',
  price: '1.0000',
  currency: 'USD',
  unit_cost: null,
  cost_currency: null,
}
const edit: EditSaved = {
  id: 5,
  shop_id: 1,
  version: 1,
  status: 'draft',
  preview_hash: 'a'.repeat(64),
  snapshot: {
    source_revision: 1,
    data_identity: 'synthetic',
    channel: 'generic',
    reason: 'Known source',
    items: [
      {
        product_id: 1,
        before: product,
        after: { ...product, name: 'New Cup' },
        source,
        result: 'pending',
        message: '等待审批',
      },
    ],
  },
  output_batch_id: null,
  created_at: '2026-10-09T00:00:00Z',
  decided_at: null,
  current_count: 0,
}
const catalog: QualityResult = {
  shop_id: 1,
  scope: { data_identity: 'synthetic', channel: 'generic', sku_prefix: '' },
  source_revision: 1,
  checked_at: '2026-10-09T00:00:00Z',
  rule_version: 'v1',
  preview_hash: 'b'.repeat(64),
  product_count: 1,
  affected_products: 0,
  missing_count: 0,
  review_count: 0,
  coverage: [],
  limitations: [],
  products: [
    {
      ...product,
      product_id: 1,
      source,
      channel: 'generic',
      issues: [],
      similar_skus: [],
      similar_sku_count: 0,
    },
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
      timezone: 'Asia/Shanghai',
      connection_status: 'file_only',
    },
  ])
  vi.mocked(productEditsApi.list).mockResolvedValue({ items: [], next_cursor: null })
  vi.mocked(productQualityApi.preview).mockResolvedValue(catalog)
  vi.mocked(productEditsApi.create).mockResolvedValue(edit)
})
afterEach(() => wrappers.splice(0).forEach((w) => w.unmount()))
async function view() {
  const wrapper = mount(ProductEditsView, {
    global: { stubs: { RouterLink: true, SupportSource: true } },
  })
  wrappers.push(wrapper)
  await flushPromises()
  return wrapper
}
async function editor() {
  const wrapper = await view()
  await wrapper.get('#edit-identity').setValue('synthetic')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  await wrapper.get('article input[type=checkbox]').setValue(true)
  await wrapper.get('#edit-name-1').setValue('New Cup')
  await wrapper.get('#edit-reason').setValue('Known source')
  return wrapper
}

it('renders untrusted differences as text and requires fresh approval for a changed version', async () => {
  const wrapper = mount(ProductEditReview, {
    props: { edit, busy: false },
    global: { stubs: { RouterLink: true, SupportSource: true } },
  })
  wrappers.push(wrapper)
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.text()).toContain(product.name)
  const approve = wrapper.findAll('button').find((b) => b.text() === '批准本地生效')!
  expect(approve.attributes('disabled')).toBeDefined()
  await wrapper.get('.edit-approval input').setValue(true)
  await wrapper.setProps({ edit: { ...edit, version: 2 } })
  expect(approve.attributes('disabled')).toBeDefined()
  await wrapper.get('.edit-approval input').setValue(true)
  await approve.trigger('click')
  expect(wrapper.emitted('decide')).toEqual([['approve']])
  await wrapper.get('.edit-control input').setValue(true)
  await wrapper.get('#edit-control').setValue('reject')
  expect(wrapper.get('.edit-control button').attributes('disabled')).toBeDefined()
})

it('discards a late catalog response when scope changes', async () => {
  let release: (value: QualityResult) => void = () => undefined
  vi.mocked(productQualityApi.preview).mockReturnValueOnce(
    new Promise((resolve) => {
      release = resolve
    }),
  )
  const wrapper = await view()
  await wrapper.get('form').trigger('submit')
  await wrapper.get('#edit-identity').setValue('synthetic')
  release(catalog)
  await flushPromises()
  expect(wrapper.find('[aria-label="编写商品修订"]').exists()).toBe(false)
})

it('saves only editable fields with source binding, hides editor and restores historical scope', async () => {
  const wrapper = await editor()
  await wrapper.get('[aria-label="编写商品修订"] form').trigger('submit')
  await flushPromises()
  expect(productEditsApi.create).toHaveBeenCalledWith(
    1,
    expect.objectContaining({
      changes: [{ product_id: 1, expected_source_row_id: 2, name: 'New Cup', facts: 'Steel' }],
      reason: 'Known source',
    }),
  )
  expect(wrapper.find('#edit-reason').exists()).toBe(false)
  expect(wrapper.findComponent(ProductEditReview).props('edit')).toEqual(edit)
  expect((wrapper.get('#edit-identity').element as HTMLSelectElement).value).toBe('synthetic')
  await wrapper.get('#edit-channel').setValue('amazon')
  expect(wrapper.findComponent(ProductEditReview).exists()).toBe(false)
})

it('replays an uncertain save with the same UUID', async () => {
  vi.mocked(productEditsApi.create).mockRejectedValueOnce(new Error('network unavailable'))
  const wrapper = await editor()
  await wrapper.get('[aria-label="编写商品修订"] form').trigger('submit')
  await flushPromises()
  const initial = vi.mocked(productEditsApi.create).mock.calls[0]![1]
  expect(wrapper.findComponent(ProductEditReview).exists()).toBe(false)
  expect(wrapper.find('#edit-reason').exists()).toBe(false)
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '回查上次保存请求')!
    .trigger('click')
  await flushPromises()
  expect(vi.mocked(productEditsApi.create).mock.calls[1]![1]).toEqual(initial)
  expect(wrapper.findComponent(ProductEditReview).exists()).toBe(true)
})

it('hides old snapshot on failed refresh and shows cleared state on readback', async () => {
  const wrapper = await editor()
  await wrapper.get('[aria-label="编写商品修订"] form').trigger('submit')
  await flushPromises()
  vi.mocked(productEditsApi.get).mockRejectedValueOnce(new Error('cannot read'))
  const refresh = wrapper.findAll('button').find((b) => b.text() === '刷新修订与来源')!
  await refresh.trigger('click')
  await flushPromises()
  expect(wrapper.findComponent(ProductEditReview).exists()).toBe(false)
  vi.mocked(productEditsApi.get).mockResolvedValueOnce({
    ...edit,
    snapshot: null,
    status: 'cleared',
    version: 2,
  })
  await refresh.trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('正文已清除')
  expect(wrapper.text()).not.toContain('Known source')
})

it('drops unsaved product text if the source revision changed', async () => {
  const wrapper = await editor()
  vi.mocked(analyticsApi.revision).mockResolvedValueOnce(2)
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '刷新修订与来源')!
    .trigger('click')
  await flushPromises()
  expect(wrapper.find('#edit-name-1').exists()).toBe(false)
  expect(wrapper.text()).toContain('来源已变化，请重新加载商品后修订')
})

it('keeps editable text when combined bulk values exceed the field limit', async () => {
  const wrapper = await editor()
  await wrapper.get('#edit-name-prefix').setValue('x'.repeat(240))
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '填入选中商品')!
    .trigger('click')
  await wrapper.get('[aria-label="编写商品修订"] form').trigger('submit')
  await flushPromises()
  expect(productEditsApi.create).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('请修正商品 A')
  expect(wrapper.find('#edit-name-1').exists()).toBe(true)
  expect((wrapper.get('#edit-reason').element as HTMLTextAreaElement).value).toBe('Known source')
})
