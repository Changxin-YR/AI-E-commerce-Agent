<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSession } from '@/composables/useSession'

const router = useRouter()
const { expire } = useSession()
function onSessionExpired(): void {
  expire()
  void router.replace('/login')
}
onMounted(() => window.addEventListener('soloops:session-expired', onSessionExpired))
onUnmounted(() => window.removeEventListener('soloops:session-expired', onSessionExpired))
</script>

<template>
  <RouterView />
</template>
