import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ListingReview from '@/components/ListingReview.vue'
import type { ListingVersion } from '@/types/listings'

function draft(): ListingVersion {
  return {
    id: 1,
    shop_id: 1,
    number: 1,
    version: 1,
    status: 'draft',
    source_status: 'current',
    base_version_id: null,
    engine: 'local_template',
    risk: 'R1',
    external_status: 'not_submitted',
    created_at: '2026-10-08T00:00:00Z',
    decided_at: null,
    snapshot: {
      product: {
        product_id: 1,
        sku: 'A',
        name: 'Cup',
        facts: 'Steel',
        source: {
          batch_id: 1,
          row_id: 1,
          row_number: 2,
          filename: 'synthetic.csv',
          sheet_name: '',
          imported_at: '2026-10-08T00:00:00Z',
          exported_at: null,
          data_identity: 'synthetic',
        },
      },
      before: { title: 'Cup', description: 'Steel' },
      proposed: { title: 'Cup', description: 'Steel' },
      missing: [],
      blockers: [],
    },
  }
}
describe('Listing review gates', () => {
  it('requires fresh confirmation and saves edits separately before approval', async () => {
    const wrapper = mount(ListingReview, {
      props: { item: draft(), busy: false, timezone: 'Asia/Shanghai', canRevise: true },
    })
    const approve = () => wrapper.findAll('button').find((b) => b.text() === '批准并在本地生效')!
    expect(approve().attributes('disabled')).toBeDefined()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    expect(approve().attributes('disabled')).toBeUndefined()
    await wrapper.get('#listing-title').setValue('Cup · Steel')
    expect(approve().attributes('disabled')).toBeDefined()
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('revise')).toEqual([[{ title: 'Cup · Steel', description: 'Steel' }]])
    expect(wrapper.emitted('decide')).toBeUndefined()
    await wrapper.setProps({ item: { ...draft(), id: 2, number: 2 } })
    expect((wrapper.get('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(false)
  })
  it('cleared sources remove editor, facts and approvals', () => {
    const wrapper = mount(ListingReview, {
      props: {
        item: { ...draft(), source_status: 'cleared', snapshot: null },
        busy: false,
        timezone: 'Asia/Shanghai',
        canRevise: false,
      },
    })
    expect(wrapper.text()).toContain('来源内容与派生文案已清除')
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Steel')
  })
})
