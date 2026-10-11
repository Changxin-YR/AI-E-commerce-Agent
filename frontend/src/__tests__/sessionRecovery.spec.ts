import { afterEach, describe, expect, it, vi } from 'vitest'
import { identityApi } from '@/api/identity'
import { useSession } from '@/composables/useSession'
import { ApiError } from '@/api/client'
import type { Session } from '@/types/identity'

afterEach(() => {
  useSession().expire()
  vi.restoreAllMocks()
})
const synthetic = { username: 'synthetic', csrf_token: 'test-token' } as Session

describe('foreground session recovery', () => {
  it('retains session on transient failure but expires confirmed 401', async () => {
    vi.spyOn(identityApi, 'login').mockResolvedValue(synthetic)
    const session = useSession()
    await session.login('synthetic', 'test')
    const read = vi.spyOn(identityApi, 'session').mockRejectedValue(new Error('offline'))
    expect(await session.refresh()).toBe(false)
    expect(session.session.value?.username).toBe('synthetic')
    read.mockRejectedValue(new ApiError('expired', 401, 'unauthorized', ''))
    expect(await session.refresh()).toBe(true)
    expect(session.session.value).toBeNull()
  })

  it('ignores an old recovery result after logout', async () => {
    let complete!: (value: Session) => void
    vi.spyOn(identityApi, 'session').mockReturnValue(
      new Promise((resolve) => {
        complete = resolve
      }),
    )
    vi.spyOn(identityApi, 'logout').mockResolvedValue(undefined)
    const session = useSession()
    const refresh = session.refresh()
    await session.logout()
    complete(synthetic)
    await refresh
    expect(session.session.value).toBeNull()
  })

  it('ignores recovery that started while logout was pending', async () => {
    let completeRead!: (value: Session) => void
    let completeLogout!: () => void
    vi.spyOn(identityApi, 'session').mockReturnValue(
      new Promise((resolve) => {
        completeRead = resolve
      }),
    )
    vi.spyOn(identityApi, 'logout').mockReturnValue(
      new Promise((resolve) => {
        completeLogout = resolve
      }),
    )
    const session = useSession()
    const logout = session.logout()
    const refresh = session.refresh()
    completeLogout()
    await logout
    completeRead(synthetic)
    await refresh
    expect(session.session.value).toBeNull()
  })
})
