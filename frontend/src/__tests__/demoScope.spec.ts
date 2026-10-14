import { expect, it, vi } from 'vitest'
import { loadDemoScope } from '@/composables/demoScope'
import type { Shop } from '@/types/identity'

const { demo } = vi.hoisted(() => ({ demo: vi.fn() }))
vi.mock('@/api/auth', () => ({ authApi: { demo } }))
const shops = [{ id: 7, code: 'demo-shop' }] as Shop[]

it('uses sample data and the demo shop only for the configured demo account', async () => {
  demo.mockResolvedValue({ enabled: true, username: 'admin' })
  expect(await loadDemoScope(shops, 'admin', {})).toEqual({
    shop: '7',
    identity: 'synthetic',
    channel: 'generic',
  })
  expect(await loadDemoScope(shops, 'seller', {})).toEqual({})
  demo.mockResolvedValue({ enabled: false })
  expect(await loadDemoScope(shops, 'admin', {})).toEqual({})
})

it('preserves explicit identity/channel and does not affect another shop', async () => {
  demo.mockResolvedValue({ enabled: true, username: 'admin' })
  expect(
    await loadDemoScope(shops, 'admin', { shop: '7', identity: 'user_import', channel: 'amazon' }),
  ).toEqual({})
  expect(await loadDemoScope(shops, 'admin', { shop: '9' })).toEqual({})
})
