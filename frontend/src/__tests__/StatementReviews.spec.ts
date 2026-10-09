import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import StatementReviews from '@/components/StatementReviews.vue'
import { statementReviewsApi as api } from '@/api/statementReviews'
import type { ReviewDraft, ReviewPreview, ReviewSaved } from '@/types/statementReviews'

vi.mock('@/api/statementReviews', () => ({
  statementReviewsApi: {
    list: vi.fn(),
    get: vi.fn(),
    preview: vi.fn(),
    write: vi.fn(),
    control: vi.fn(),
    current: vi.fn(),
  },
}))
const scope: ReviewDraft['scope'] = {
  data_identity: 'synthetic',
  channel: 'generic',
  timezone: 'UTC',
  start_at: '2026-10-07T00:00:00Z',
  end_at: '2026-10-08T00:00:00Z',
}
const conclusion = {
  outcome: 'pending' as const,
  note: '<img src=x onerror=alert(1)> Seller evidence',
}
const preview: ReviewPreview = {
  preview_hash: 'a'.repeat(64),
  snapshot: {
    conclusion,
    expense_revision: 5,
    blockers: ['费用缺失待核'],
    result: {
      scope,
      source_revision: 3,
      rule_revision: 4,
      calculated_at: '2026-10-09T00:00:00Z',
      statements: [],
      totals: [],
      comparisons: [],
      mappings: [],
      stale_expenses: 0,
      withdrawn_expenses: 0,
      checks: [],
    },
  },
}
const saved: ReviewSaved = {
  id: 2,
  shop_id: 1,
  data_identity: 'synthetic',
  channel: 'generic',
  status: 'active',
  version: 1,
  content_version: 1,
  created_at: '2026-10-09T00:00:00Z',
  snapshot: preview.snapshot,
  history: [{ version: 1, action: 'create', conclusion, created_at: '2026-10-09T00:00:00Z' }],
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
  const w = mount(StatementReviews, {
    props: { shopId: 1, scope, disabled: false, freshness: 0, initialId },
    global: { stubs: { RouterLink: true, StatementResult: true } },
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
async function editing(w: Wrapper) {
  await click(w, '新建核对结论')
  await w.get('#review-note').setValue(conclusion.note)
  await w.get('form').trigger('submit')
  await flushPromises()
}
it('binds preview and explicit confirmation to every conclusion edit, escaping text', async () => {
  const w = setup()
  await editing(w)
  expect(w.find('img').exists()).toBe(false)
  expect(w.text()).toContain(conclusion.note)
  expect(
    w
      .findAll('button')
      .find((b) => b.text() === '保存核对结论')!
      .attributes('disabled'),
  ).toBeDefined()
  await w.get('input[type=checkbox]').setValue(true)
  await w.get('#review-outcome').setValue('consistent')
  expect(w.find('[aria-label="核对结论预览"]').exists()).toBe(false)
  expect(api.write).not.toHaveBeenCalled()
})
it('keeps the exact unknown write request and hides old evidence before retry', async () => {
  const w = setup()
  await editing(w)
  await w.get('input[type=checkbox]').setValue(true)
  vi.mocked(api.write).mockRejectedValueOnce(new Error('network'))
  await click(w, '保存核对结论')
  const body = vi.mocked(api.write).mock.calls[0]![1]
  expect(w.find('[aria-label="核对结论预览"]').exists()).toBe(false)
  expect(w.find('[role=alert]').exists()).toBe(true)
  await click(w, '回查原结论保存请求')
  expect(vi.mocked(api.write).mock.calls[1]![1]).toEqual(body)
  expect(w.text()).toContain('核对 #2 · 当前有效 · 版本 1')
})
it('drops a late preview on focus and range changes', async () => {
  const w = setup()
  let resolve!: (v: ReviewPreview) => void
  vi.mocked(api.preview).mockReturnValue(
    new Promise((r) => {
      resolve = r
    }),
  )
  await editing(w)
  window.dispatchEvent(new Event('focus'))
  resolve(preview)
  await flushPromises()
  expect(w.find('[aria-label="核对结论预览"]').exists()).toBe(false)
  await w.setProps({ scope: { ...scope, channel: 'amazon' } })
  expect(w.find('form').exists()).toBe(false)
})
it('hides the entire old detail if current read or list refresh fails', async () => {
  const w = setup(2)
  await flushPromises()
  expect(w.text()).toContain(conclusion.note)
  vi.mocked(api.current).mockRejectedValueOnce(new Error('unavailable'))
  await click(w, '回读当前来源、费用与规则')
  expect(w.text()).not.toContain(conclusion.note)
  expect(w.find('[role=alert]').exists()).toBe(true)
  vi.mocked(api.list).mockRejectedValueOnce(new Error('list unavailable'))
  await click(w, '读取核对存档')
  expect(w.text()).toContain('list unavailable')
})
it('uses the saved historical scope for revision and never reactivates on current read', async () => {
  vi.mocked(api.current).mockResolvedValue({
    record: { ...saved, status: 'stale', version: 2 },
    preview,
  })
  const w = setup(2)
  await flushPromises()
  await click(w, '回读当前来源、费用与规则')
  expect(w.text()).toContain('依据已变化 · 待重核')
  expect(api.get).toHaveBeenCalledTimes(1)
  expect(api.write).not.toHaveBeenCalled()
  await click(w, '修订并重新核对')
  await w.get('form').trigger('submit')
  await flushPromises()
  expect(vi.mocked(api.preview).mock.calls[0]![1]).toEqual({
    scope,
    review_id: 2,
    version: 2,
    conclusion,
  })
})
it('shows source-cleared status from the atomic current response with no old body', async () => {
  const w = setup(2)
  await flushPromises()
  vi.mocked(api.current).mockResolvedValue({
    record: { ...saved, status: 'cleared', version: 2, snapshot: null, history: [] },
    preview: null,
  })
  await click(w, '回读当前来源、费用与规则')
  expect(w.text()).not.toContain(conclusion.note)
  expect(w.text()).toContain('正文及全部历史依据已清除')
  expect(w.find('[aria-label="存档当前依据"]').exists()).toBe(false)
})
it('clears all visible history and binds control consent to the chosen action', async () => {
  const w = setup(2)
  await flushPromises()
  await w.get('input[type=checkbox]').setValue(true)
  await w.get('#review-control').setValue('clear')
  expect((w.get('input[type=checkbox]').element as HTMLInputElement).checked).toBe(false)
  await w.get('input[type=checkbox]').setValue(true)
  vi.mocked(api.control).mockResolvedValue({
    ...saved,
    status: 'cleared',
    version: 2,
    snapshot: null,
    history: [],
  })
  await click(w, '确认处理结论')
  expect(w.text()).not.toContain(conclusion.note)
  expect(w.text()).toContain('正文及全部历史依据已清除')
})
it('invalidates saved evidence on rule changes and ignores late unmounted reads', async () => {
  const w = setup(2)
  await flushPromises()
  await w.setProps({ freshness: 1 })
  expect(w.text()).not.toContain(conclusion.note)
  let resolve!: (value: { items: ReviewSaved[]; next_cursor: null }) => void
  vi.mocked(api.list).mockReturnValue(
    new Promise((r) => {
      resolve = r
    }),
  )
  await click(w, '读取核对存档')
  w.unmount()
  resolve({ items: [saved], next_cursor: null })
  await flushPromises()
  expect(api.write).not.toHaveBeenCalled()
})
