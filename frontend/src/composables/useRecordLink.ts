import { onBeforeUnmount } from 'vue'
import { useRoute, useRouter, type LocationQueryRaw } from 'vue-router'

// The caller handles external navigation; its own URL updates preserve live edits.
export function useRecordLink() {
  const route = useRoute()
  const router = useRouter()
  const ownerPath = route.path
  let active = true
  onBeforeUnmount(() => {
    active = false
  })
  let ownPath = ''
  function isOwn(path: string, consume = true): boolean {
    if (path !== ownPath) return false
    if (consume) ownPath = ''
    return true
  }
  async function write(query: LocationQueryRaw, replace = false): Promise<void> {
    if (!active || route.path !== ownerPath) return
    const target = { path: ownerPath, query }
    ownPath = router.resolve(target).fullPath
    if (ownPath === route.fullPath) {
      ownPath = ''
      return
    }
    if (replace) await router.replace(target)
    else await router.push(target)
  }
  return { write, isOwn }
}
