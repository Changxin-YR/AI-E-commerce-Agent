import { flushPromises, mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import SellerNavigation from '@/components/SellerNavigation.vue'

it('opens the current group, preserves all 19 routes and toggles accessible disclosure controls', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  await router.push('/listings?shop=2&listing=8')
  const wrapper = mount(SellerNavigation, { global: { plugins: [router] } })
  await flushPromises()
  expect(wrapper.find('a[href="/listings"]').attributes('aria-current')).toBe('page')
  const groups = wrapper.findAll('.group-toggle')
  expect(groups[1]!.attributes('aria-expanded')).toBe('true')
  expect(groups[4]!.attributes('aria-expanded')).toBe('false')
  await groups[4]!.trigger('click')
  expect(groups[4]!.attributes('aria-expanded')).toBe('true')
  await wrapper.find('.all-functions').trigger('click')
  expect(wrapper.findAll('a')).toHaveLength(19)
  expect(groups.every((button) => button.attributes('aria-expanded') === 'true')).toBe(true)
  await wrapper.find('.all-functions').trigger('click')
  expect(groups.every((button) => button.attributes('aria-expanded') === 'false')).toBe(true)
  await router.push('/support?shop=2&draft=3')
  await flushPromises()
  expect(groups[2]!.attributes('aria-expanded')).toBe('true')
  expect(wrapper.find('a[href="/support"]').attributes('aria-current')).toBe('page')
  wrapper.unmount()
})
