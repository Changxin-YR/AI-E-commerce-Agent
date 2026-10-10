<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSession } from '@/composables/useSession'
import { errorMessage } from '@/api/client'
import FeedbackBanner from './FeedbackBanner.vue'
import ReturnToTask from './ReturnToTask.vue'
import SellerNavigation from './SellerNavigation.vue'

const router = useRouter()
const { session, logout } = useSession()
const error = ref('')
const busy = ref(false)
async function signOut(): Promise<void> {
  busy.value = true
  error.value = ''
  try {
    await logout()
    await router.push('/login')
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="app-layout">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <aside class="sidebar">
      <RouterLink to="/" class="wordmark" aria-label="SoloOps 首页"
        ><span class="brand-mark" aria-hidden="true"></span>SoloOps<span class="brand-dot"
          >.</span
        ></RouterLink
      >
      <p class="sidebar-caption">你的独立经营工作台</p>
      <SellerNavigation />
      <div class="sidebar-bottom">
        <div class="mode-status"><span></span>文件分析模式</div>
        <p>从你提供的数据出发，<br />让每个经营判断有据可查。</p>
        <div class="account-row">
          <span class="avatar">{{ session?.username.slice(0, 1).toUpperCase() }}</span
          ><span>{{ session?.username }}</span
          ><button class="signout" :disabled="busy" @click="signOut">退出</button>
        </div>
      </div>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <span>个人卖家工作空间</span><span class="local-label">本地数据 · 由你掌控</span>
      </header>
      <main id="main-content" tabindex="-1">
        <FeedbackBanner :message="error" /><ReturnToTask /><RouterView
          :key="['/agent', '/support'].includes($route.path) ? $route.path : $route.fullPath"
        />
      </main>
    </div>
  </div>
</template>
