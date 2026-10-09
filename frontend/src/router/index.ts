import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import { useSession } from '@/composables/useSession'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    {
      path: '/',
      component: AppShell,
      children: [
        { path: '', component: () => import('@/views/DashboardView.vue') },
        { path: 'settings', component: () => import('@/views/SettingsView.vue') },
        { path: 'imports', component: () => import('@/views/ImportsView.vue') },
        { path: 'analytics', component: () => import('@/views/AnalyticsView.vue') },
        { path: 'listings', component: () => import('@/views/ListingsView.vue') },
        { path: 'support', component: () => import('@/views/SupportView.vue') },
        { path: 'inventory', component: () => import('@/views/InventoryView.vue') },
        { path: 'agent', component: () => import('@/views/AgentView.vue') },
        { path: 'profit', component: () => import('@/views/ProfitView.vue') },
        { path: 'rules', component: () => import('@/views/RulesView.vue') },
        { path: 'outbound', component: () => import('@/views/OutboundView.vue') },
        { path: 'overview', component: () => import('@/views/OverviewView.vue') },
        { path: 'schedules', component: () => import('@/views/SchedulesView.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const { session, initialize } = useSession()
  await initialize()
  if (!session.value && to.name !== 'login') return { name: 'login' }
  if (session.value && to.name === 'login') return '/'
})

export default router
