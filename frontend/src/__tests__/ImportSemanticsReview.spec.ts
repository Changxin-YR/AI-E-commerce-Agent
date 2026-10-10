import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ImportSemanticsReview from '@/components/ImportSemanticsReview.vue'

describe('import meaning review', () => {
  it('requires an explicit selection and renders source labels as text', async () => {
    const wrapper = mount(ImportSemanticsReview, {
      props: {
        reviews: [
          {
            field: 'refund',
            column: '<img src=x onerror=bad()>',
            label: '行退款',
            meaning: '仅该行退款',
          },
        ],
        modelValue: [],
        disabled: false,
      },
    })
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('<img src=x onerror=bad()>')
    expect((wrapper.get('input').element as HTMLInputElement).checked).toBe(false)
    await wrapper.get('input').setValue(true)
    expect(wrapper.emitted('update:modelValue')).toEqual([[['refund']]])
    await wrapper.setProps({ disabled: true })
    expect(wrapper.get('fieldset').attributes()).toHaveProperty('disabled')
  })
})
