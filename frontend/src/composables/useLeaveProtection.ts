import { onUnmounted, ref } from 'vue'

const checks = new Set<() => boolean>()
const blockers = new Set<() => boolean>()
export const leavePrompt = ref(false)
export const leaveBlocked = ref(false)
let resolvePrompt: ((answer: boolean) => void) | undefined
let pending: Promise<boolean> | undefined

export function finishLeaving(answer: boolean): void {
  leavePrompt.value = false
  resolvePrompt?.(answer)
  resolvePrompt = undefined
  pending = undefined
}

export function confirmLeaving(): Promise<boolean> {
  leaveBlocked.value = [...blockers].some((check) => check())
  if (!leaveBlocked.value && ![...checks].some((check) => check())) return Promise.resolve(true)
  pending ??= new Promise<boolean>((resolve) => {
    resolvePrompt = resolve
    leavePrompt.value = true
  })
  return pending
}

/** Register live dirty state; never persist customer form values on the device. */
export function useLeaveProtection(check: () => boolean, blocked = () => false): void {
  checks.add(check)
  blockers.add(blocked)
  onUnmounted(() => {
    checks.delete(check)
    blockers.delete(blocked)
  })
}
