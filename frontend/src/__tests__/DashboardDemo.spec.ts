import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'

const { demo, onboarding, shops } = vi.hoisted(() => ({
  demo: vi.fn(),
  onboarding: vi.fn(),
  shops: vi.fn(),
}))
vi.mock('@/api/auth', () => ({ authApi: { demo } }))
vi.mock('@/api/identity', () => ({ identityApi: { onboarding, shops } }))
vi.mock('@/composables/useSession', () => ({
  useSession: () => ({ session: { value: { username: 'admin' } } }),
}))

beforeEach(() => {
  demo.mockResolvedValue({ enabled: true, username: 'admin' })
  shops.mockResolvedValue([{ id: 7, code: 'demo-shop' }])
  onboarding.mockResolvedValue({ shop_count: 1, profile_complete: true })
})

it.each([
  ['/', 'synthetic'],
  ['/?shop=7&identity=user_import', 'user_import'],
])('initializes dashboard shortcuts with the correct scope: %s', async (location, identity) => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  await router.push(location)
  const wrapper = mount(DashboardView, {
    global: { plugins: [router], stubs: ['WorkInbox', 'OperationsInbox', 'AiWorkspaceActions'] },
  })
  await flushPromises()
  expect(router.currentRoute.value.query).toMatchObject({ shop: '7', identity })
  const link = wrapper.get('.page-heading a')
  expect(link.attributes('href')).toContain('shop=7')
  expect(link.attributes('href')).toContain(`identity=${identity}`)
  expect(wrapper.find('work-inbox-stub').exists()).toBe(true)
  wrapper.unmount()
})
