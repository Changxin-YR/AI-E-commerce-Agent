<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { agentApi } from '@/api/agent'
import type { ModelStatus } from '@/types/agent'
import AppIcon from './AppIcon.vue'

const props = defineProps<{ scope: Record<string, string> }>()
const model = ref<ModelStatus | null>(null)
const status = computed(() => {
  if (!props.scope.shop) return '选择店铺后开始'
  if (!model.value) return '查看模型配置'
  if (model.value.status !== 'configured') return '模型待配置'
  return model.value.provider === 'deepseek_chat' ? 'DeepSeek 已连接' : '模型已配置'
})
watch(
  () => props.scope.shop,
  async (shop, _previous, cleanup) => {
    let active = true
    cleanup(() => {
      active = false
    })
    model.value = null
    if (!shop) return
    try {
      const result = await agentApi.model(Number(shop))
      if (active) model.value = result
    } catch {
      /* The task page provides detailed configuration errors. */
    }
  },
  { immediate: true },
)
const actions = [
  { mode: 'question', icon: 'chart', title: 'AI 经营问数', detail: '从销售与成本中找到经营重点' },
  {
    mode: 'listing_model',
    icon: 'package',
    title: 'AI Listing',
    detail: '根据商品事实生成文案候选',
  },
  {
    mode: 'support_model',
    icon: 'messages',
    title: 'AI 客服',
    detail: '结合消息与订单准备回复草稿',
  },
  {
    mode: 'daily_model',
    icon: 'clipboard',
    title: 'AI 今日运营',
    detail: '检查异常并整理可执行待办',
  },
]
</script>

<template>
  <section class="ai-workspace" aria-labelledby="ai-workspace-title">
    <div class="ai-workspace-heading">
      <div>
        <span class="ai-eyebrow"><AppIcon name="sparkles" :size="16" />AI 经营助手</span>
        <h2 id="ai-workspace-title">把经营问题交给 AI，从这里开始。</h2>
        <p>使用当前店铺的数据，保留事实依据，生成结果后由你审阅。</p>
      </div>
      <RouterLink :to="{ path: '/agent', query: scope }" class="ai-model-status"
        >{{ status }}<AppIcon name="chevron" :size="14"
      /></RouterLink>
    </div>
    <div class="ai-actions">
      <RouterLink
        v-for="action in actions"
        :key="action.mode"
        class="ai-action"
        :to="{ path: '/agent', query: { ...scope, mode: action.mode } }"
      >
        <span class="quick-icon"><AppIcon :name="action.icon" :size="23" /></span>
        <strong>{{ action.title }}</strong>
        <span>{{ action.detail }}</span>
        <AppIcon class="ai-action-arrow" name="arrow" :size="17" />
      </RouterLink>
    </div>
  </section>
</template>
