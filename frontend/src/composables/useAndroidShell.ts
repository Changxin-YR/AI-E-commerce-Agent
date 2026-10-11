import { onMounted, onUnmounted, ref } from 'vue'
import { Capacitor, type PluginListenerHandle } from '@capacitor/core'
import { App } from '@capacitor/app'
import { Network } from '@capacitor/network'
import { Keyboard } from '@capacitor/keyboard'
import type { Router } from 'vue-router'
import { finishLeaving, leavePrompt } from './useLeaveProtection'
import { useSession } from './useSession'

export const nativeAndroid = Capacitor.getPlatform() === 'android'
export const navigationOpen = ref(false)
export const connectionNotice = ref('')
export const checkingConnection = ref(false)
let wasOffline = false

export async function checkConnection(quiet = false): Promise<void> {
  if (checkingConnection.value) return
  checkingConnection.value = true
  try {
    const status = await Network.getStatus()
    if (!status.connected) {
      wasOffline = true
      connectionNotice.value = '网络已断开，当前输入会保留。连接恢复后可重试未完成的操作。'
      return
    }
    const restored = await useSession().refresh()
    connectionNotice.value =
      restored && quiet && !wasOffline
        ? ''
        : restored
          ? '连接已恢复，当前输入已保留。请按页面提示重新读取或检查操作结果。'
          : '暂时无法连接服务，当前输入已保留。请稍后检查连接。'
    wasOffline = !restored
  } finally {
    checkingConnection.value = false
  }
}

export function useAndroidShell(router: Router): void {
  const handles: PluginListenerHandle[] = []
  let disposed = false
  const listen = async (handle: Promise<PluginListenerHandle>) => {
    const value = await handle
    if (disposed) await value.remove()
    else handles.push(value)
  }
  const networkFailure = () => {
    wasOffline = true
    connectionNotice.value = '暂时无法连接服务，当前输入已保留。请检查连接后重试。'
  }
  onMounted(async () => {
    if (!nativeAndroid) return
    window.addEventListener('soloops:network-error', networkFailure)
    await listen(
      App.addListener('backButton', () => {
        if (leavePrompt.value) return finishLeaving(false)
        if (navigationOpen.value) {
          navigationOpen.value = false
          return
        }
        const current = router.currentRoute.value
        if (current.path === '/' || current.path === '/login') void App.minimizeApp()
        else if (
          router.options.history.state.back &&
          router.options.history.state.back !== '/login'
        )
          router.back()
        else void router.push('/')
      }),
    )
    await listen(
      Network.addListener('networkStatusChange', ({ connected }) => {
        if (!connected) networkFailure()
        else if (wasOffline) void checkConnection()
      }),
    )
    await listen(
      App.addListener('appStateChange', ({ isActive }) => {
        if (isActive) void checkConnection(true)
      }),
    )
    await listen(
      Keyboard.addListener('keyboardDidShow', () => {
        document.documentElement.classList.add('keyboard-open')
        document.activeElement?.scrollIntoView({ block: 'center', behavior: 'smooth' })
      }),
    )
    await listen(
      Keyboard.addListener('keyboardDidHide', () => {
        document.documentElement.classList.remove('keyboard-open')
      }),
    )
    const status = await Network.getStatus()
    if (!status.connected) networkFailure()
  })
  onUnmounted(() => {
    disposed = true
    window.removeEventListener('soloops:network-error', networkFailure)
    for (const handle of handles) void handle.remove()
  })
}
