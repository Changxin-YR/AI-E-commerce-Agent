<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { workspaceQuery } from '@/composables/deepLink'
import AppIcon from './AppIcon.vue'

const route = useRoute()
const groups = [
  {
    name: '今日 AI 运营',
    icon: 'sparkles',
    links: [
      ['/', '工作台'],
      ['/imports', '数据导入'],
      ['/agent', '任务执行台'],
    ],
  },
  {
    name: '商品与选品',
    icon: 'package',
    links: [
      ['/listings', 'Listing 审批'],
      ['/inventory', '库存快照'],
      ['/profit', '新品利润'],
      ['/product-quality', '商品质量'],
      ['/product-edits', '商品修订'],
    ],
  },
  {
    name: '订单与客服',
    icon: 'messages',
    links: [
      ['/support', '客服工作台'],
      ['/order-reconciliation', '订单销售与退款核对'],
    ],
  },
  {
    name: '经营与财务',
    icon: 'chart',
    links: [
      ['/analytics', '经营分析'],
      ['/overview', '经营总览'],
      ['/expenses', '实际费用'],
      ['/statements', '账单核对'],
      ['/settlements', '结算与回款'],
    ],
  },
  {
    name: '自动化与设置',
    icon: 'settings',
    links: [
      ['/settings', '经营资料'],
      ['/rules', '经营规则'],
      ['/outbound', '邮件外发'],
      ['/schedules', '定时与通知'],
    ],
  },
] as const
const linkIcons: Record<string, string> = {
  '/': 'home',
  '/imports': 'upload',
  '/agent': 'clipboard',
  '/listings': 'check',
  '/inventory': 'package',
  '/profit': 'wallet',
  '/product-quality': 'shield',
  '/product-edits': 'edit',
  '/support': 'messages',
  '/order-reconciliation': 'receipt',
  '/analytics': 'chart',
  '/overview': 'grid',
  '/expenses': 'wallet',
  '/statements': 'file',
  '/settlements': 'wallet',
  '/settings': 'settings',
  '/rules': 'clipboard',
  '/outbound': 'send',
  '/schedules': 'calendar',
}
const expanded = ref<number[]>([])
const allOpen = computed(() => expanded.value.length === groups.length)
watch(
  () => route.path,
  (path) => {
    const index = groups.findIndex((group) => group.links.some(([url]) => url === path))
    if (index >= 0 && !expanded.value.includes(index)) expanded.value.push(index)
  },
  { immediate: true },
)
function toggle(index: number): void {
  expanded.value = expanded.value.includes(index)
    ? expanded.value.filter((value) => value !== index)
    : [...expanded.value, index]
}
</script>

<template>
  <nav class="seller-navigation" aria-label="主导航">
    <button
      class="all-functions"
      :aria-expanded="allOpen"
      aria-controls="seller-groups"
      @click="expanded = allOpen ? [] : groups.map((_, index) => index)"
    >
      <AppIcon name="grid" :size="18" />
      <span>{{ allOpen ? '收起全部功能' : '展开全部功能' }}</span>
      <AppIcon name="chevron" :size="16" class="disclosure" :class="{ expanded: allOpen }" />
    </button>
    <div id="seller-groups">
      <div v-for="(group, index) in groups" :key="group.name" class="nav-group">
        <button
          class="group-toggle"
          :aria-expanded="expanded.includes(index)"
          :aria-controls="`seller-group-${index}`"
          @click="toggle(index)"
        >
          <AppIcon :name="group.icon" />
          <span>{{ group.name }}</span>
          <AppIcon
            name="chevron"
            :size="16"
            class="disclosure"
            :class="{ expanded: expanded.includes(index) }"
          />
        </button>
        <ul v-show="expanded.includes(index)" :id="`seller-group-${index}`">
          <li v-for="[url, label] in group.links" :key="url">
            <RouterLink
              :to="{ path: url, query: workspaceQuery(route.query) }"
              exact-active-class="active"
            >
              <AppIcon :name="linkIcons[url] ?? 'file'" :size="18" />
              <span>{{ label }}</span>
            </RouterLink>
          </li>
        </ul>
      </div>
    </div>
  </nav>
</template>
