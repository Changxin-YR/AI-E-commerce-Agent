<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { isNavigationFailure, NavigationFailureType, useRoute, useRouter } from 'vue-router'
import { useSession } from '@/composables/useSession'
import { workspaceQuery } from '@/composables/deepLink'
import { errorMessage } from '@/api/client'
import FeedbackBanner from './FeedbackBanner.vue'
import ReturnToTask from './ReturnToTask.vue'
import SellerNavigation from './SellerNavigation.vue'
import AppIcon from './AppIcon.vue'

const router = useRouter()
const route = useRoute()
const { session, logout } = useSession()
const error = ref('')
const busy = ref(false)
const mobileMenuOpen = ref(false)
const menuToggle = ref<HTMLButtonElement | null>(null)
const mainContent = ref<HTMLElement | null>(null)
const pageTitles: Record<string, string> = {
  '/': '工作台',
  '/imports': '数据导入',
  '/agent': '任务执行台',
  '/listings': 'Listing 审批',
  '/inventory': '库存快照',
  '/profit': '新品利润',
  '/product-quality': '商品质量',
  '/product-edits': '商品修订',
  '/support': '客服工作台',
  '/order-reconciliation': '订单销售与退款核对',
  '/analytics': '经营分析',
  '/overview': '经营总览',
  '/expenses': '实际费用',
  '/statements': '账单核对',
  '/settlements': '结算与回款',
  '/settings': '经营资料',
  '/rules': '经营规则',
  '/outbound': '邮件外发',
  '/schedules': '定时与通知',
}
const pageTitle = computed(() => pageTitles[route.path] ?? '工作空间')

async function closeMobileMenu(): Promise<void> {
  if (!mobileMenuOpen.value) return
  mobileMenuOpen.value = false
  await nextTick()
  menuToggle.value?.focus()
}

function toggleMobileMenu(): void {
  if (mobileMenuOpen.value) void closeMobileMenu()
  else mobileMenuOpen.value = true
}

const removeNavigationHook = router.afterEach(async (_to, _from, failure) => {
  if (
    !mobileMenuOpen.value ||
    (failure && !isNavigationFailure(failure, NavigationFailureType.duplicated))
  )
    return
  mobileMenuOpen.value = false
  await nextTick()
  mainContent.value?.focus()
})

let mobileViewport: MediaQueryList | undefined
function handleViewportChange(event: MediaQueryListEvent): void {
  if (!event.matches) mobileMenuOpen.value = false
}
onMounted(() => {
  if (typeof window.matchMedia !== 'function') return
  mobileViewport = window.matchMedia('(max-width: 760px)')
  mobileViewport.addEventListener('change', handleViewportChange)
})
onUnmounted(() => {
  removeNavigationHook()
  mobileViewport?.removeEventListener('change', handleViewportChange)
})

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
    <aside class="sidebar" @keydown.esc="closeMobileMenu">
      <div class="sidebar-brand">
        <div>
          <RouterLink
            :to="{ path: '/', query: workspaceQuery(route.query) }"
            class="wordmark"
            aria-label="SoloOps 首页"
          >
            <span class="brand-mark" aria-hidden="true"><AppIcon name="leaf" :size="23" /></span>
            SoloOps<span class="brand-dot">.</span>
          </RouterLink>
          <p class="sidebar-caption">你的独立经营工作台</p>
        </div>
        <button
          ref="menuToggle"
          type="button"
          class="mobile-menu-toggle"
          :aria-expanded="mobileMenuOpen"
          aria-controls="sidebar-navigation"
          :aria-label="mobileMenuOpen ? '收起导航菜单' : '展开导航菜单'"
          @click="toggleMobileMenu"
        >
          <AppIcon :name="mobileMenuOpen ? 'close' : 'menu'" />
          <span>{{ mobileMenuOpen ? '收起' : '菜单' }}</span>
        </button>
      </div>
      <div id="sidebar-navigation" class="sidebar-content" :class="{ 'is-open': mobileMenuOpen }">
        <RouterLink
          class="sidebar-ai"
          :to="{ path: '/agent', query: { ...workspaceQuery(route.query), mode: 'question' } }"
        >
          <AppIcon name="sparkles" :size="20" /><span
            ><strong>AI 经营助手</strong><small>问数 · 文案 · 客服 · 运营</small></span
          ><AppIcon name="arrow" :size="16" />
        </RouterLink>
        <SellerNavigation />
        <div class="sidebar-bottom">
          <div class="mode-status"><span></span>受控经营助手</div>
          <p>从你提供的数据出发，<br />让每个经营判断有据可查。</p>
          <div class="account-row">
            <span class="avatar">{{ session?.username.slice(0, 1).toUpperCase() }}</span>
            <div class="account-copy">
              <span class="account-name">{{ session?.username }}</span>
              <span class="account-role">独立卖家</span>
            </div>
            <button class="signout" :disabled="busy" @click="signOut">
              {{ busy ? '退出中…' : '退出' }}
            </button>
          </div>
        </div>
      </div>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <div class="breadcrumb">
          <span>个人卖家工作空间</span>
          <AppIcon name="chevron" :size="14" />
          <span class="current-page">{{ pageTitle }}</span>
        </div>
        <RouterLink
          class="topbar-ai"
          :to="{ path: '/agent', query: { ...workspaceQuery(route.query), mode: 'question' } }"
          ><AppIcon name="sparkles" :size="16" />AI 助手</RouterLink
        >
      </header>
      <main id="main-content" ref="mainContent" tabindex="-1">
        <FeedbackBanner :message="error" /><ReturnToTask /><RouterView
          :key="['/', '/agent', '/support'].includes($route.path) ? $route.path : $route.fullPath"
        />
      </main>
    </div>
  </div>
</template>

<style scoped>
.mobile-menu-toggle {
  display: none;
}

@media (max-width: 760px) {
  .mobile-menu-toggle {
    display: inline-flex;
  }

  .sidebar-content {
    display: none;
  }

  .sidebar-content.is-open {
    display: block;
  }
}
</style>
