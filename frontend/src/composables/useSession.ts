import { readonly, ref } from 'vue'
import { ApiError, errorMessage, setCsrfToken } from '@/api/client'
import { identityApi } from '@/api/identity'
import type { Session } from '@/types/identity'

const session = ref<Session | null>(null)
const connectionError = ref('')
let initialization: Promise<void> | undefined
let sessionEpoch = 0

function applySession(value: Session | null): void {
  sessionEpoch++
  session.value = value
  setCsrfToken(value?.csrf_token ?? '')
}

export function useSession() {
  async function initialize(): Promise<void> {
    initialization ??= identityApi
      .session()
      .then(applySession)
      .catch((error: unknown) => {
        if (!(error instanceof ApiError && error.status === 401))
          connectionError.value = errorMessage(error)
      })
    return initialization
  }
  async function login(username: string, password: string): Promise<void> {
    sessionEpoch++
    applySession(await identityApi.login(username, password))
    connectionError.value = ''
  }
  async function logout(): Promise<void> {
    sessionEpoch++
    await identityApi.logout()
    applySession(null)
  }
  async function refresh(): Promise<boolean> {
    const epoch = sessionEpoch
    try {
      const value = await identityApi.session()
      if (epoch !== sessionEpoch) return true
      applySession(value)
      connectionError.value = ''
      window.dispatchEvent(new Event('soloops:session-restored'))
      return true
    } catch (error) {
      if (epoch !== sessionEpoch) return true
      if (error instanceof ApiError && error.status === 401) {
        applySession(null)
        window.dispatchEvent(new Event('soloops:session-expired'))
        return true
      }
      connectionError.value = errorMessage(error)
      return false
    }
  }
  return {
    session: readonly(session),
    connectionError: readonly(connectionError),
    initialize,
    login,
    logout,
    refresh,
    expire: () => {
      sessionEpoch++
      applySession(null)
    },
  }
}
