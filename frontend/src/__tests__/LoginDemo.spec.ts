import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import LoginView from '@/views/LoginView.vue'

const { demo, login } = vi.hoisted(() => ({ demo: vi.fn(), login: vi.fn() }))
vi.mock('@/api/auth', () => ({ authApi: { demo } }))
vi.mock('@/composables/useSession', () => ({ useSession: () => ({ login, connectionError: '' }) }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace: vi.fn() }),
}))
beforeEach(() => vi.clearAllMocks())

it('shows enabled demo credentials below login and fills them without submitting', async () => {
  demo.mockResolvedValue({ enabled: true, username: 'admin', password: 'qwer123' })
  const wrapper = mount(LoginView)
  await flushPromises()
  expect(wrapper.get('[aria-label="演示账号"]').text()).toContain('admin')
  expect(wrapper.get('[aria-label="演示账号"]').text()).toContain('qwer123')
  await wrapper.get('[aria-label="演示账号"] button').trigger('click')
  expect((wrapper.get('#username').element as HTMLInputElement).value).toBe('admin')
  expect((wrapper.get('#password').element as HTMLInputElement).value).toBe('qwer123')
  expect(login).not.toHaveBeenCalled()
})

it.each([{ enabled: false }, { enabled: true }])(
  'hides incomplete or disabled demo metadata: %j',
  async (value) => {
    demo.mockResolvedValue(value)
    const wrapper = mount(LoginView)
    await flushPromises()
    expect(wrapper.find('[aria-label="演示账号"]').exists()).toBe(false)
    expect(wrapper.find('#username').exists()).toBe(true)
  },
)

it('keeps normal sign-in available if demo metadata is unavailable', async () => {
  demo.mockRejectedValue(new Error('metadata unavailable'))
  const wrapper = mount(LoginView)
  await flushPromises()
  expect(wrapper.find('[aria-label="演示账号"]').exists()).toBe(false)
  expect(wrapper.find('button[type="button"]').exists()).toBe(false)
})
