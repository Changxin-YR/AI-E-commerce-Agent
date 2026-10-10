<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const groups = [
  {
    name: '今日 AI 运营',
    links: [
      ['/', '工作台'],
      ['/imports', '数据导入'],
      ['/agent', '任务执行台'],
    ],
  },
  {
    name: '商品与选品',
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
    links: [
      ['/support', '客服工作台'],
      ['/order-reconciliation', '订单销售与退款核对'],
    ],
  },
  {
    name: '经营与财务',
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
    links: [
      ['/settings', '经营资料'],
      ['/rules', '经营规则'],
      ['/outbound', '测试外发'],
      ['/schedules', '定时与通知'],
    ],
  },
] as const
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
      {{ allOpen ? '收起全部功能' : '展开全部功能' }}
      <span aria-hidden="true">{{ allOpen ? '−' : '+' }}</span>
    </button>
    <div id="seller-groups">
      <div v-for="(group, index) in groups" :key="group.name" class="nav-group">
        <button
          class="group-toggle"
          :aria-expanded="expanded.includes(index)"
          :aria-controls="`seller-group-${index}`"
          @click="toggle(index)"
        >
          <span class="nav-number">0{{ index + 1 }}</span
          >{{ group.name }}
          <span class="disclosure" aria-hidden="true">{{
            expanded.includes(index) ? '−' : '+'
          }}</span>
        </button>
        <ul v-show="expanded.includes(index)" :id="`seller-group-${index}`">
          <li v-for="[url, label] in group.links" :key="url">
            <RouterLink :to="url" exact-active-class="active">{{ label }}</RouterLink>
          </li>
        </ul>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.seller-navigation {
  display: block;
  margin-top: 24px;
}
.all-functions,
.group-toggle {
  display: flex;
  align-items: center;
  width: 100%;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.all-functions {
  justify-content: space-between;
  color: #b7c3af;
  padding: 8px 4px 14px;
  font-size: 12px;
}
.nav-group {
  border-top: 1px solid #ffffff18;
  padding: 3px 0;
}
.group-toggle {
  gap: 9px;
  padding: 12px 2px;
  font-size: 13px;
}
.disclosure {
  margin-left: auto;
  color: #b7c3af;
}
.nav-group ul {
  list-style: none;
  padding: 0 0 8px 17px;
  margin: 0;
}
.nav-group a {
  padding: 9px 11px;
  font-size: 12px;
}
@media (max-width: 760px) {
  .seller-navigation {
    margin-top: 12px;
  }
  .group-toggle {
    padding: 10px 2px;
  }
  .nav-group ul {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    padding-left: 20px;
  }
  .nav-group a {
    padding: 8px 10px;
  }
}
</style>
