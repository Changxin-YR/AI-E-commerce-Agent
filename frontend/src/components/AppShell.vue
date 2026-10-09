<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSession } from '@/composables/useSession'
import { errorMessage } from '@/api/client'
import FeedbackBanner from './FeedbackBanner.vue'

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
      <nav aria-label="主导航">
        <RouterLink to="/" exact-active-class="active"
          ><span class="nav-number">01</span>工作台</RouterLink
        ><RouterLink to="/settings" active-class="active"
          ><span class="nav-number">02</span>经营资料</RouterLink
        ><RouterLink to="/imports" active-class="active"
          ><span class="nav-number">03</span>数据导入</RouterLink
        ><RouterLink to="/analytics" active-class="active"
          ><span class="nav-number">04</span>经营分析</RouterLink
        ><RouterLink to="/listings" active-class="active"
          ><span class="nav-number">05</span>Listing 审批</RouterLink
        ><RouterLink to="/support" active-class="active"
          ><span class="nav-number">06</span>客服工作台</RouterLink
        ><RouterLink to="/inventory" active-class="active"
          ><span class="nav-number">07</span>库存快照</RouterLink
        ><RouterLink to="/agent" active-class="active"
          ><span class="nav-number">08</span>任务执行台</RouterLink
        ><RouterLink to="/profit" active-class="active"
          ><span class="nav-number">09</span>新品利润</RouterLink
        ><RouterLink to="/rules" active-class="active"
          ><span class="nav-number">10</span>经营规则</RouterLink
        ><RouterLink to="/outbound" active-class="active"
          ><span class="nav-number">11</span>测试外发</RouterLink
        ><RouterLink to="/overview" active-class="active"
          ><span class="nav-number">12</span>经营总览</RouterLink
        ><RouterLink to="/schedules" active-class="active"
          ><span class="nav-number">13</span>定时与通知</RouterLink
        ><RouterLink to="/product-quality" active-class="active"
          ><span class="nav-number">14</span>商品质量</RouterLink
        >
      </nav>
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
        <FeedbackBanner :message="error" /><RouterView :key="$route.fullPath" />
      </main>
    </div>
  </div>
</template>
