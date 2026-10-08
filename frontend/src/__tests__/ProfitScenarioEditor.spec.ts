import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import ProfitScenarioEditor from '@/components/ProfitScenarioEditor.vue'
import { decimalText, newScenario } from '@/types/profit'

it('keeps blank fees unknown and requires evidence for explicit zero', async () => {
  const model = newScenario()
  const wrapper = mount(ProfitScenarioEditor, {
    props: { modelValue: model, index: 0, currency: 'USD' },
  })
  const value = wrapper.get('#fee-value-0-tax')
  const basis = wrapper.get('#fee-basis-0-tax')
  expect(basis.attributes('required')).toBeUndefined()
  await value.setValue('0')
  expect(model.fees.find((fee) => fee.kind === 'tax')?.value).toBe('0')
  expect(basis.attributes('required')).toBeDefined()
  await value.setValue('')
  expect(model.fees.find((fee) => fee.kind === 'tax')?.value).toBeNull()
  expect(basis.attributes('required')).toBeUndefined()
})

it('preserves exact monetary text without binary number conversion', async () => {
  const model = newScenario()
  const wrapper = mount(ProfitScenarioEditor, {
    props: { modelValue: model, index: 0, currency: 'USD' },
  })
  await wrapper.get('#scenario-price-0').setValue('99999999.9999')
  expect(model.price).toBe('99999999.9999')
  expect(decimalText('123456789123456.12000000100')).toBe('123456789123456.120000001')
  expect(decimalText(null)).toBe('无法确定')
  expect(decimalText('0.0000')).toBe('0')
})
