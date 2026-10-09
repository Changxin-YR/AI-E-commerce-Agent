import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import FeeRules from '@/components/FeeRules.vue'
import { feeRulesApi } from '@/api/feeRules'
import type { FeeRuleDraft, FeeRulePreview, FeeRuleSaved } from '@/types/feeRules'

vi.mock('@/api/feeRules', () => ({
  feeRulesApi: {
    list: vi.fn(),
    get: vi.fn(),
    preview: vi.fn(),
    write: vi.fn(),
    control: vi.fn(),
  },
}))
const scope: FeeRuleDraft['scope'] = {
  data_identity: 'synthetic',
  channel: 'generic',
  timezone: 'UTC',
  start_at: '2026-10-07T00:00:00Z',
  end_at: '2026-10-08T00:00:00Z',
}
const content = {
  fee_name: '<img src=x onerror=alert(1)>',
  category: 'platform' as const,
  reason: 'Seller definition',
}
const saved: FeeRuleSaved = {
  id: 2,
  shop_id: 1,
  data_identity: 'synthetic',
  channel: 'generic',
  content,
  status: 'active',
  version: 1,
  created_at: '2026-10-09T00:00:00Z',
  history: [],
}
const preview: FeeRulePreview = {
  preview_hash: 'a'.repeat(64),
  source_revision: 2,
  calculated_at: '2026-10-09T00:00:00Z',
  previous: null,
  proposed: content,
  changes: [],
  statement_count: 0,
  scope,
}
const wrappers: { unmount: () => void }[] = []
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(feeRulesApi.list).mockResolvedValue({ items: [saved], next_cursor: null })
  vi.mocked(feeRulesApi.get).mockResolvedValue(saved)
  vi.mocked(feeRulesApi.preview).mockResolvedValue(preview)
  vi.mocked(feeRulesApi.write).mockResolvedValue(saved)
})
afterEach(() => wrappers.splice(0).forEach((w) => w.unmount()))
function setup() {
  const wrapper = mount(FeeRules, { props: { shopId: 1, scope, disabled: false } })
  wrappers.push(wrapper)
  return wrapper
}
type Wrapper = ReturnType<typeof setup>
async function click(w: Wrapper, name: string) {
  const button = w.findAll('button').find((b) => b.text() === name)
  expect(button).toBeTruthy()
  await button!.trigger('click')
  await flushPromises()
}
async function editing(w: Wrapper) {
  await click(w, '新建映射规则')
  await w.get('#fee-rule-name').setValue(content.fee_name)
  await w.get('#fee-rule-reason').setValue(content.reason)
  await w.get('form').trigger('submit')
  await flushPromises()
}
it('requires preview confirmation and clears consent when content changes', async () => {
  const w = setup()
  await editing(w)
  expect(w.find('img').exists()).toBe(false)
  expect(w.text()).toContain('全部日期与币种')
  expect(
    w
      .findAll('button')
      .find((b) => b.text() === '保存规则并回读')!
      .attributes('disabled'),
  ).toBeDefined()
  await w.get('input[type="checkbox"]').setValue(true)
  await w.get('#fee-rule-category').setValue('tax')
  expect(w.find('[aria-label="规则差异预览"]').exists()).toBe(false)
  expect(feeRulesApi.write).not.toHaveBeenCalled()
})
it('replays the exact unknown write request and hides old content', async () => {
  const w = setup()
  await editing(w)
  await w.get('input[type="checkbox"]').setValue(true)
  vi.mocked(feeRulesApi.write).mockRejectedValueOnce(new Error('network'))
  await click(w, '保存规则并回读')
  const body = vi.mocked(feeRulesApi.write).mock.calls[0]![1]
  expect(w.find('[aria-label="规则差异预览"]').exists()).toBe(false)
  await click(w, '回查原规则保存请求')
  expect(vi.mocked(feeRulesApi.write).mock.calls[1]![1]).toEqual(body)
  expect(w.text()).toContain('规则 #2 · 有效 · 版本 1')
  expect(w.emitted('changed')).toHaveLength(1)
})
it('drops a late preview after focus invalidation', async () => {
  const w = setup()
  let resolve!: (value: FeeRulePreview) => void
  vi.mocked(feeRulesApi.preview).mockReturnValue(
    new Promise((r) => {
      resolve = r
    }),
  )
  await editing(w)
  window.dispatchEvent(new Event('focus'))
  resolve(preview)
  await flushPromises()
  expect(w.find('[aria-label="规则差异预览"]').exists()).toBe(false)
  expect(w.find('form').exists()).toBe(false)
})
it('clears detail before a failed refresh and drops unmounted reads', async () => {
  const w = setup()
  await click(w, '读取规则列表')
  await click(w, `规则 #2 · ${content.fee_name} · 有效 · v1`)
  expect(w.text()).toContain(content.reason)
  vi.mocked(feeRulesApi.list).mockRejectedValueOnce(new Error('unavailable'))
  await click(w, '读取规则列表')
  expect(w.text()).not.toContain(content.reason)
  expect(w.find('[role="alert"]').exists()).toBe(true)
  let resolve!: (value: { items: FeeRuleSaved[]; next_cursor: null }) => void
  vi.mocked(feeRulesApi.list).mockReturnValue(
    new Promise((r) => {
      resolve = r
    }),
  )
  await click(w, '读取规则列表')
  w.unmount()
  resolve({ items: [saved], next_cursor: null })
  await flushPromises()
  expect(w.emitted('changed')).toBeUndefined()
})
it('binds control confirmation to action and clears all displayed rule history', async () => {
  const w = setup()
  await click(w, '读取规则列表')
  await click(w, `规则 #2 · ${content.fee_name} · 有效 · v1`)
  await w.get('input[type="checkbox"]').setValue(true)
  await w.get('#fee-rule-control').setValue('clear')
  expect((w.get('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(false)
  await w.get('input[type="checkbox"]').setValue(true)
  vi.mocked(feeRulesApi.control).mockResolvedValue({
    ...saved,
    content: null,
    status: 'cleared',
    version: 2,
    history: [],
  })
  await click(w, '确认处理规则')
  expect(w.text()).not.toContain(content.fee_name)
  expect(w.text()).toContain('收费名、类别及全部历史正文已清除')
  expect(vi.mocked(feeRulesApi.control).mock.calls[0]![2]).toBe('clear')
})
