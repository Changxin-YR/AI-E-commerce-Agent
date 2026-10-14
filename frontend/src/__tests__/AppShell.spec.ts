import { flushPromises, mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import AppShell from '@/components/AppShell.vue'

it('keeps the selected shop and source on sidebar navigation without carrying record IDs', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  await router.push('/?shop=3&identity=synthetic&channel=amazon&task=42')
  const wrapper = mount(AppShell, { global: { plugins: [router] } })
  try {
    await wrapper.get('.seller-navigation a[href^="/imports"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/imports')
    expect(router.currentRoute.value.query).toEqual({
      shop: '3',
      identity: 'synthetic',
      channel: 'amazon',
    })
  } finally {
    wrapper.unmount()
  }
})

it('closes mobile navigation on successful or repeated routes, preserves cancelled navigation and restores focus', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  await router.push('/')
  const wrapper = mount(AppShell, { attachTo: document.body, global: { plugins: [router] } })
  const menu = wrapper.get('.mobile-menu-toggle')
  const main = wrapper.get('#main-content')

  try {
    await menu.trigger('click')
    expect(menu.attributes('aria-expanded')).toBe('true')
    await wrapper.get('.seller-navigation a[href="/"]').trigger('click')
    await flushPromises()
    expect(menu.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(main.element)

    await menu.trigger('click')
    const removeGuard = router.beforeEach(() => false)
    await wrapper.get('.seller-navigation a[href="/imports"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/')
    expect(menu.attributes('aria-expanded')).toBe('true')
    removeGuard()

    await wrapper.get('.seller-navigation a[href="/imports"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/imports')
    expect(menu.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(main.element)

    await menu.trigger('click')
    await wrapper.get('.sidebar').trigger('keydown', { key: 'Escape' })
    expect(menu.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(menu.element)
  } finally {
    wrapper.unmount()
  }
})
