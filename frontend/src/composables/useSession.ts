import { readonly, ref } from 'vue'
import { ApiError, errorMessage, setCsrfToken } from '@/api/client'
import { identityApi } from '@/api/identity'
import type { Session } from '@/types/identity'

const session = ref<Session | null>(null)
const connectionError = ref('')
let initialization: Promise<void> | undefined

function applySession(value: Session | null): void {
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
    applySession(await identityApi.login(username, password))
    connectionError.value = ''
  }
  async function logout(): Promise<void> {
    await identityApi.logout()
    applySession(null)
  }
  return {
    session: readonly(session),
    connectionError: readonly(connectionError),
    initialize,
    login,
    logout,
    expire: () => applySession(null),
  }
}
