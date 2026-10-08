import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ImportRows from '@/components/ImportRows.vue'
import type { ImportRow } from '@/types/imports'

describe('import row evidence', () => {
  it('escapes source markup and emits corrections without overwriting evidence', async () => {
    const row: ImportRow = {
      row_number: 2,
      raw: { name: '<script>bad()</script>' },
      normalized: {},
      previous: null,
      corrections: {},
      errors: [{ field: 'name', message: 'Check' }],
      warnings: [],
      action: 'error',
    }
    const wrapper = mount(ImportRows, {
      props: {
        rows: [row],
        fields: [{ key: 'name', label: '商品名', data_type: '文本', required: true, help: '' }],
        editable: true,
        corrections: {},
        disabled: false,
      },
    })
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.text()).toContain('<script>bad()</script>')
    await wrapper.get('input[aria-label="源行 2 商品名 修正值"]').setValue('Verified name')
    expect(wrapper.emitted('correct')).toEqual([[2, 'name', 'Verified name']])
    expect(row.raw.name).toBe('<script>bad()</script>')
  })
})
