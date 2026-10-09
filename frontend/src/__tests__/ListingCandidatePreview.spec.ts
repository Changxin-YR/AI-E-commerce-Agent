import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import ListingCandidatePreview from '@/components/ListingCandidatePreview.vue'
import type { ListingCandidate } from '@/types/agent'

it('keeps the base and full restrictions visible while escaping source text', () => {
  const value: ListingCandidate = {
    engine: 'test_double',
    preparation: {
      active_id: 7,
      before: { title: 'Bottle', description: '仅限冷水' },
      product: {
        product_id: 1,
        sku: 'B',
        name: 'Bottle',
        facts: '仅限冷水\n<script>bad</script>',
        source: {
          row_id: 1,
          batch_id: 1,
          row_number: 2,
          filename: 'synthetic.csv',
          sheet_name: '',
          imported_at: '2026-10-09T00:00:00Z',
          exported_at: null,
          data_identity: 'synthetic',
        },
      },
    },
    candidate: { title: 'Bottle', description: '<script>bad</script>\n仅限冷水' },
  }
  const wrapper = mount(ListingCandidatePreview, { props: { value } })
  expect(wrapper.text()).toContain('本地版本 #7')
  expect(wrapper.text()).toContain('仅限冷水')
  expect(wrapper.text()).toContain('<script>bad</script>')
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.text()).toContain('单独批准')
  expect(wrapper.text()).toContain('有文字变化')
})
