<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSession } from '@/composables/useSession'
import { nativeAndroid, useAndroidShell } from '@/composables/useAndroidShell'
import AndroidStatus from '@/components/AndroidStatus.vue'

const router = useRouter()
useAndroidShell(router)
const { expire, session } = useSession()
function onSessionRestored(): void {
  if (session.value && router.currentRoute.value.path === '/login') void router.replace('/')
}
function onSessionExpired(): void {
  expire()
  void router.replace('/login')
}
onMounted(() => window.addEventListener('soloops:session-expired', onSessionExpired))
onUnmounted(() => window.removeEventListener('soloops:session-expired', onSessionExpired))
onMounted(() => window.addEventListener('soloops:session-restored', onSessionRestored))
onUnmounted(() => window.removeEventListener('soloops:session-restored', onSessionRestored))
</script>

<template>
  <RouterView />
  <AndroidStatus v-if="nativeAndroid" />
</template>
