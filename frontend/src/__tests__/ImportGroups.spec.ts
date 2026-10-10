import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ImportGroups from '@/components/ImportGroups.vue'
import type { ImportGroup } from '@/types/imports'

const api = vi.hoisted(() => ({ groups: vi.fn(), group: vi.fn(), revokeGroup: vi.fn() }))
vi.mock('@/api/imports', () => ({ importsApi: api }))
const fixture = (id: number, shop: number): ImportGroup => ({
  id,
  shop_id: shop,
  version: 2,
  status: 'active',
  complete: false,
  options: {
    kind: 'orders',
    source_channel: 'generic',
    data_identity: 'synthetic',
    timezone: 'UTC',
  },
  manifest: {
    format: 'soloops-split-v1',
    source_filename: '<img src=x>.csv',
    source_sha256: 'a'.repeat(64),
    total_rows: 2001,
    parts: [
      { filename: 'part-001.csv', sha256: 'a'.repeat(64), rows: 2000, bytes: 300 },
      { filename: 'part-002.csv', sha256: 'b'.repeat(64), rows: 1, bytes: 60 },
    ],
  },
  batches: [],
  committed_parts: 0,
  committed_rows: 0,
  unique_rows: 0,
  overlap_rows: 0,
})
const props = { shopId: 1, options: {}, refresh: 0, disabled: false }
beforeEach(() => vi.resetAllMocks())
describe('import groups', () => {
  it('drops a late response after the seller selects another shop', async () => {
    let finish!: (value: ImportGroup[]) => void
    api.groups
      .mockImplementationOnce(
        () =>
          new Promise<ImportGroup[]>((resolve) => {
            finish = resolve
          }),
      )
      .mockResolvedValueOnce([fixture(2, 2)])
    const wrapper = mount(ImportGroups, { props })
    await wrapper.setProps({ shopId: 2 })
    await flushPromises()
    finish([fixture(1, 1)])
    await flushPromises()
    expect(wrapper.findAll('option').map((option) => option.attributes('value'))).toEqual([
      '0',
      '2',
    ])
    await wrapper.get('select').setValue('2')
    expect(wrapper.text()).toContain('部分覆盖／数据不足')
    expect(wrapper.find('img').exists()).toBe(false)
  })
  it('lets the seller cancel the group rollback and binds confirmation to its version', async () => {
    const group = fixture(1, 1)
    api.groups.mockResolvedValue([group])
    api.revokeGroup.mockResolvedValue({ ...group, status: 'revoked' })
    const wrapper = mount(ImportGroups, { props })
    await flushPromises()
    await wrapper.get('select').setValue('1')
    const button = (text: string) => wrapper.findAll('button').find((item) => item.text() === text)!
    await button('撤销整组').trigger('click')
    await button('继续保留').trigger('click')
    expect(api.revokeGroup).not.toHaveBeenCalled()
    await button('撤销整组').trigger('click')
    await button('确认撤销整组').trigger('click')
    await flushPromises()
    expect(api.revokeGroup).toHaveBeenCalledExactlyOnceWith(1, 2)
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })
})
