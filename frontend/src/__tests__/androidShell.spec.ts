import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import type { Router } from 'vue-router'

const mocks = vi.hoisted(() => ({
  listeners: new Map<string, (value?: never) => void>(),
  remove: vi.fn(),
  minimize: vi.fn(),
  refresh: vi.fn(),
  status: vi.fn(),
}))
vi.mock('@capacitor/core', () => ({ Capacitor: { getPlatform: () => 'android' } }))
vi.mock('@capacitor/app', () => ({
  App: {
    addListener: async (event: string, handler: (value?: never) => void) => {
      mocks.listeners.set(event, handler)
      return { remove: mocks.remove }
    },
    minimizeApp: mocks.minimize,
  },
}))
vi.mock('@capacitor/network', () => ({
  Network: {
    addListener: async (event: string, handler: (value?: never) => void) => {
      mocks.listeners.set(event, handler)
      return { remove: mocks.remove }
    },
    getStatus: mocks.status,
  },
}))
vi.mock('@capacitor/keyboard', () => ({
  Keyboard: {
    addListener: async (event: string, handler: (value?: never) => void) => {
      mocks.listeners.set(event, handler)
      return { remove: mocks.remove }
    },
  },
}))
vi.mock('@/composables/useSession', () => ({ useSession: () => ({ refresh: mocks.refresh }) }))
import {
  checkConnection,
  connectionNotice,
  navigationOpen,
  useAndroidShell,
} from '@/composables/useAndroidShell'
import {
  confirmLeaving,
  finishLeaving,
  leavePrompt,
  useLeaveProtection,
} from '@/composables/useLeaveProtection'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.listeners.clear()
  mocks.status.mockResolvedValue({ connected: true })
  mocks.refresh.mockResolvedValue(true)
  navigationOpen.value = false
  connectionNotice.value = ''
})
afterEach(() => finishLeaving(false))

describe('Android shell', () => {
  it('closes navigation first, routes through Vue guards, and minimizes only at root', async () => {
    const router = {
      currentRoute: { value: { path: '/settings' } },
      options: { history: { state: { back: '/' } } },
      back: vi.fn(),
      push: vi.fn(),
    }
    const wrapper = mount(
      defineComponent({
        setup() {
          useAndroidShell(router as unknown as Router)
          return () => null
        },
      }),
    )
    await flushPromises()
    navigationOpen.value = true
    mocks.listeners.get('backButton')?.()
    expect(navigationOpen.value).toBe(false)
    expect(router.back).not.toHaveBeenCalled()
    mocks.listeners.get('backButton')?.()
    expect(router.back).toHaveBeenCalledOnce()
    router.options.history.state.back = '/login'
    mocks.listeners.get('backButton')?.()
    expect(router.push).toHaveBeenCalledWith('/')
    router.currentRoute.value.path = '/'
    mocks.listeners.get('backButton')?.()
    expect(mocks.minimize).toHaveBeenCalledOnce()
    wrapper.unmount()
    expect(mocks.remove).toHaveBeenCalledTimes(5)
  })

  it('keeps dirty edits on cancellation, coalesces prompts, and unregisters on unmount', async () => {
    const wrapper = mount(
      defineComponent({
        setup() {
          useLeaveProtection(() => true)
          return () => null
        },
      }),
    )
    const first = confirmLeaving()
    expect(confirmLeaving()).toBe(first)
    expect(leavePrompt.value).toBe(true)
    finishLeaving(false)
    expect(await first).toBe(false)
    const second = confirmLeaving()
    finishLeaving(true)
    expect(await second).toBe(true)
    wrapper.unmount()
    expect(await confirmLeaving()).toBe(true)
  })

  it('does not issue session requests offline; recovery checks session without replaying writes', async () => {
    mocks.status.mockResolvedValue({ connected: false })
    await checkConnection()
    expect(connectionNotice.value).toContain('网络已断开')
    expect(mocks.refresh).not.toHaveBeenCalled()
    mocks.status.mockResolvedValue({ connected: true })
    await checkConnection()
    expect(mocks.refresh).toHaveBeenCalledOnce()
    expect(connectionNotice.value).toContain('连接已恢复')
    await checkConnection(true)
    expect(connectionNotice.value).toBe('')
  })
})
