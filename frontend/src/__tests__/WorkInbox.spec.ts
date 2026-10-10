import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import WorkInbox from '@/components/WorkInbox.vue'
import { workbenchApi } from '@/api/workbench'
import type { WorkItem, WorkPage } from '@/types/workbench'
import { identityApi } from '@/api/identity'
import type { Shop } from '@/types/identity'

const route = vi.hoisted(() => ({ query: {} as Record<string, string> }))
vi.mock('vue-router', () => ({ useRoute: () => route }))
vi.mock('@/api/workbench', () => ({ workbenchApi: { list: vi.fn() } }))
vi.mock('@/api/identity', () => ({ identityApi: { shops: vi.fn().mockResolvedValue([]) } }))
beforeEach(() => {
  route.query = {}
  vi.mocked(identityApi.shops).mockResolvedValue([])
})
const result = (label: string): WorkPage => ({
  items: [
    {
      kind: 'listing',
      id: 1,
      target_id: 1,
      label,
      detail: '',
      status: 'draft',
      source_status: 'current',
      bucket: 'approval',
      view: 'attention',
      business_state: null,
      review_current: false,
      shop_id: 2,
      shop_name: '合成店',
      timezone: 'UTC',
      data_identity: 'synthetic',
      channel: 'generic',
      risk: 'R1',
      created_at: '2026-10-09T00:00:00Z',
      due_at: null,
      path: '/listings',
      query: { shop: '2', listing: '1' },
    } satisfies WorkItem,
  ],
  counts: { approval: 1 },
  view_counts: { attention: 1 },
  recent_runs: [],
  next_cursor: null,
  read_at: '2026-10-09T00:00:00Z',
})

it('drops a previous scope response and renders imported text without interpreting it', async () => {
  let release: (value: WorkPage) => void = () => undefined
  vi.mocked(workbenchApi.list)
    .mockReturnValueOnce(
      new Promise((resolve) => {
        release = resolve
      }),
    )
    .mockResolvedValueOnce(result('<script>ignore permissions</script>'))
  const wrapper = mount(WorkInbox, { global: { stubs: { RouterLink: RouterLinkStub } } })
  await flushPromises()
  await wrapper.findAll('select')[1]!.setValue('synthetic')
  await flushPromises()
  release(result('previous-scope'))
  await flushPromises()
  expect(wrapper.text()).not.toContain('previous-scope')
  expect(wrapper.text()).toContain('<script>ignore permissions</script>')
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.text()).toContain('等待审批')
  expect(wrapper.text()).not.toContain('等待 R2 审批')
  const links = wrapper.findAllComponents(RouterLinkStub).map((c) => c.props('to'))
  expect(links).toContainEqual({ path: '/listings', query: { shop: '2', listing: '1' } })
  wrapper.unmount()
})

it('defaults to an existing shop and explicit identity, keeps scoped links and server view counts', async () => {
  vi.mocked(identityApi.shops).mockResolvedValue([
    { id: 2, name: '合成店', timezone: 'UTC' } as Shop,
  ])
  route.query = { shop: '2', identity: 'synthetic', channel: 'generic' }
  vi.mocked(workbenchApi.list).mockResolvedValue({
    ...result('review'),
    view_counts: { attention: 47, ai_completed: 23, update_data: 9 },
  })
  const wrapper = mount(WorkInbox, { global: { stubs: { RouterLink: RouterLinkStub } } })
  await flushPromises()
  expect(workbenchApi.list).toHaveBeenLastCalledWith(
    expect.objectContaining({ shop_id: '2', data_identity: 'synthetic', view: 'attention' }),
    undefined,
  )
  expect(wrapper.find('[aria-label="卖家工作视图"]').text()).toContain('47')
  await wrapper.find('[aria-label="卖家工作视图"]').findAll('button')[1]!.trigger('click')
  expect(workbenchApi.list).toHaveBeenLastCalledWith(
    expect.objectContaining({ view: 'ai_completed', bucket: '' }),
    undefined,
  )
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '继续审批')!
    .trigger('click')
  expect(workbenchApi.list).toHaveBeenLastCalledWith(
    expect.objectContaining({ view: '', bucket: 'approval' }),
    undefined,
  )
  expect(wrapper.findAllComponents(RouterLinkStub).map((c) => c.props('to'))).toContainEqual({
    path: '/imports',
    query: { shop: '2', identity: 'synthetic', channel: 'generic' },
  })
  wrapper.unmount()
})

it('rejects an inaccessible linked shop without loading another scope', async () => {
  route.query = { shop: '999' }
  vi.mocked(workbenchApi.list).mockClear()
  const wrapper = mount(WorkInbox, { global: { stubs: { RouterLink: true } } })
  await flushPromises()
  expect(wrapper.text()).toContain('店铺不存在或无权访问')
  expect(workbenchApi.list).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('clears cached items when focus refresh fails and ignores an earlier late error', async () => {
  let fail: (reason: Error) => void = () => undefined
  vi.mocked(workbenchApi.list)
    .mockResolvedValueOnce(result('initial'))
    .mockReturnValueOnce(
      new Promise((_, reject) => {
        fail = reject
      }),
    )
    .mockResolvedValueOnce(result('new-scope'))
    .mockRejectedValueOnce(new Error('refresh failed'))
  const wrapper = mount(WorkInbox, { global: { stubs: { RouterLink: true } } })
  await flushPromises()
  window.dispatchEvent(new Event('focus'))
  await wrapper.findAll('select')[1]!.setValue('synthetic')
  await flushPromises()
  fail(new Error('late error'))
  await flushPromises()
  expect(wrapper.text()).toContain('new-scope')
  expect(wrapper.text()).not.toContain('late error')
  window.dispatchEvent(new Event('focus'))
  await flushPromises()
  expect(wrapper.text()).not.toContain('new-scope')
  expect(wrapper.text()).toContain('refresh failed')
  wrapper.unmount()
})
