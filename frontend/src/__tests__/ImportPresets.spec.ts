import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ImportPresets from '@/components/ImportPresets.vue'
import type { ImportPreset } from '@/types/imports'

const preset: ImportPreset = {
  id: 'shopify-products-2026-10-10-v1',
  name: 'Shopify 商品 CSV',
  kind: 'products',
  source_channel: 'shopify',
  verified_on: '2026-10-10',
  reference_url: 'https://help.shopify.com/en/manual/products/import-export/using-csv',
  mapping: { sku: 'SKU', name: 'Title' },
  notes: ['请补齐币种', '<script>invalid()</script>'],
}

describe('verified import candidates', () => {
  it('shows evidence and requires a click before applying a candidate', async () => {
    const wrapper = mount(ImportPresets, { props: { presets: [preset], disabled: false } })
    expect(wrapper.emitted('apply')).toBeUndefined()
    expect(wrapper.text()).toContain('2026-10-10')
    expect(wrapper.get('a').attributes('href')).toBe(preset.reference_url)
    expect(wrapper.find('script').exists()).toBe(false)
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('apply')).toEqual([[preset.id]])
    await wrapper.setProps({ disabled: true })
    expect(wrapper.get('button').attributes()).toHaveProperty('disabled')
  })
  it('does not advertise a candidate for unmatched or retired formats', () => {
    const wrapper = mount(ImportPresets, { props: { presets: [], disabled: false } })
    expect(wrapper.find('section').exists()).toBe(false)
  })
})
