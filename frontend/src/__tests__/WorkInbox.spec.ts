import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import WorkInbox from '@/components/WorkInbox.vue'
import { workbenchApi } from '@/api/workbench'
import type { WorkItem, WorkPage } from '@/types/workbench'

vi.mock('@/api/workbench', () => ({ workbenchApi: { list: vi.fn() } }))
vi.mock('@/api/identity', () => ({ identityApi: { shops: vi.fn().mockResolvedValue([]) } }))
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
