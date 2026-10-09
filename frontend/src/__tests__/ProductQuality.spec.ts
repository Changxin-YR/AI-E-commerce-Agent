import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ProductQualityResult from '@/components/ProductQualityResult.vue'
import ProductQualityView from '@/views/ProductQualityView.vue'
import { productQualityApi } from '@/api/productQuality'
import { identityApi } from '@/api/identity'
import { analyticsApi } from '@/api/analytics'
import type { QualityResult } from '@/types/productQuality'

vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('@/api/productQuality', () => ({
  productQualityApi: {
    preview: vi.fn(),
    save: vi.fn(),
    list: vi.fn(),
    get: vi.fn(),
    clear: vi.fn(),
  },
}))
vi.mock('@/api/identity', () => ({ identityApi: { shops: vi.fn() } }))
vi.mock('@/api/analytics', () => ({ analyticsApi: { revision: vi.fn() } }))
const result: QualityResult = {
  shop_id: 1,
  scope: { data_identity: 'synthetic', channel: null, sku_prefix: '' },
  source_revision: 2,
  checked_at: '2026-10-09T00:00:00Z',
  rule_version: 'product-quality-v1',
  preview_hash: 'a'.repeat(64),
  product_count: 2,
  affected_products: 1,
  missing_count: 1,
  review_count: 0,
  coverage: [{ code: 'media', label: '图片', status: 'not_checked', reason: '没有图片字段' }],
  limitations: [],
  products: [
    {
      product_id: 1,
      sku: 'A',
      name: '<script>alert(1)</script>',
      facts: '',
      price: null,
      currency: null,
      unit_cost: '0.0000',
      cost_currency: 'USD',
      channel: 'generic',
      source: {
        batch_id: 1,
        row_id: 1,
        row_number: 2,
        filename: 'synthetic.csv',
        sheet_name: '',
        exported_at: null,
        imported_at: '2026-10-08T00:00:00Z',
        data_identity: 'synthetic',
      },
      issues: [
        {
          code: 'facts_missing',
          field: 'facts',
          status: 'missing',
          reason: '参数缺失',
          suggestion: '补充来源',
        },
      ],
      similar_skus: [],
      similar_sku_count: 0,
    },
    {
      product_id: 2,
      sku: 'B',
      name: 'Cup',
      facts: 'Steel',
      price: '1.0000',
      currency: 'USD',
      unit_cost: '0.0000',
      cost_currency: 'USD',
      channel: 'generic',
      source: {
        batch_id: 1,
        row_id: 2,
        row_number: 3,
        filename: 'synthetic.csv',
        sheet_name: '',
        exported_at: null,
        imported_at: '2026-10-08T00:00:00Z',
        data_identity: 'synthetic',
      },
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
  vi.mocked(productQualityApi.list).mockResolvedValue({ items: [], next_cursor: null })
  vi.mocked(productQualityApi.preview).mockResolvedValue(result)
})
afterEach(() => {
  wrappers.splice(0).forEach((w) => w.unmount())
})
async function view() {
  const wrapper = mount(ProductQualityView, {
    global: { stubs: { RouterLink: true, SourceEvidence: true } },
  })
  wrappers.push(wrapper)
  await flushPromises()
  return wrapper
}

it('filters findings, preserves unknown and zero, and renders source text as text', async () => {
  const wrapper = mount(ProductQualityResult, {
    props: { result, timezone: 'Asia/Shanghai' },
    global: { stubs: { SourceEvidence: true } },
  })
  wrappers.push(wrapper)
  expect(wrapper.text()).toContain('0.0000 USD')
  expect(wrapper.text()).toContain('未知')
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.text()).toContain('<script>alert(1)</script>')
  await wrapper.get('#quality-filter').setValue('missing')
  expect(wrapper.findAll('article')).toHaveLength(1)
  await wrapper.get('#quality-filter').setValue('none')
  expect(wrapper.text()).toContain('品牌、编码、素材等未检查项仍需核验')
  expect(wrapper.findAll('article')).toHaveLength(1)
  await wrapper.get('#quality-search').setValue('absent')
  expect(wrapper.text()).toContain('没有匹配筛选的商品')
})

it('discards a late preview after a scope change', async () => {
  let release: (value: QualityResult) => void = () => undefined
  vi.mocked(productQualityApi.preview).mockReturnValueOnce(
    new Promise((resolve) => {
      release = resolve
    }),
  )
  const wrapper = await view()
  await wrapper.get('form').trigger('submit')
  await wrapper.get('#quality-identity').setValue('synthetic')
  release(result)
  await flushPromises()
  expect(wrapper.findComponent(ProductQualityResult).exists()).toBe(false)
})

it('clears confirmation on scope changes and hides old source text when save fails', async () => {
  const wrapper = await view()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  await wrapper.get('input[type="checkbox"]').setValue(true)
  await wrapper.get('#quality-prefix').setValue('A')
  expect(wrapper.findComponent(ProductQualityResult).exists()).toBe(false)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.get<HTMLInputElement>('input[type="checkbox"]').element.checked).toBe(false)
  vi.mocked(productQualityApi.save).mockRejectedValueOnce(new Error('来源已变化'))
  await wrapper.get('input[type="checkbox"]').setValue(true)
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '保存检查报告')!
    .trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('来源已变化')
  expect(wrapper.findComponent(ProductQualityResult).exists()).toBe(false)
})

it('refresh removes an unsaved snapshot after a source revision changes', async () => {
  const wrapper = await view()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  vi.mocked(analyticsApi.revision).mockResolvedValueOnce(3)
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '刷新报告与来源')!
    .trigger('click')
  await flushPromises()
  expect(wrapper.findComponent(ProductQualityResult).exists()).toBe(false)
  expect(wrapper.text()).toContain('来源已变化，请重新检查')
})

it('restores the saved report scope when opening history', async () => {
  const report = {
    id: 8,
    shop_id: 1,
    status: 'current' as const,
    created_at: result.checked_at,
    scope: result.scope,
    snapshot: result,
  }
  vi.mocked(productQualityApi.list).mockResolvedValueOnce({
    items: [{ ...report, snapshot: null }],
    next_cursor: null,
  })
  vi.mocked(productQualityApi.get).mockResolvedValueOnce(report)
  const wrapper = await view()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '查看报告 #8')!
    .trigger('click')
  await flushPromises()
  expect(wrapper.get<HTMLSelectElement>('#quality-identity').element.value).toBe('synthetic')
  expect(wrapper.findComponent(ProductQualityResult).exists()).toBe(true)
})

it('erases the displayed SKU prefix together with a cleared report', async () => {
  const report = {
    id: 8,
    shop_id: 1,
    status: 'current' as const,
    created_at: result.checked_at,
    scope: { ...result.scope, sku_prefix: 'A' },
    snapshot: result,
  }
  vi.mocked(productQualityApi.list).mockResolvedValueOnce({
    items: [{ ...report, snapshot: null }],
    next_cursor: null,
  })
  vi.mocked(productQualityApi.get).mockResolvedValueOnce(report)
  vi.mocked(productQualityApi.clear).mockResolvedValueOnce({
    ...report,
    status: 'cleared',
    snapshot: null,
    scope: { ...report.scope, sku_prefix: '' },
  })
  const wrapper = await view()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '查看报告 #8')!
    .trigger('click')
  await flushPromises()
  await wrapper.get('input[type="checkbox"]').setValue(true)
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '清除报告正文')!
    .trigger('click')
  await flushPromises()
  expect(wrapper.get<HTMLInputElement>('#quality-prefix').element.value).toBe('')
  expect(wrapper.findComponent(ProductQualityResult).exists()).toBe(false)
  expect(wrapper.text()).toContain('正文已清除')
})
