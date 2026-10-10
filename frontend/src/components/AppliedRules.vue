<script setup lang="ts">
import { ref, watch } from 'vue'
import { rulesApi, type BusinessRule } from '@/api/businessRules'
import { errorMessage } from '@/api/client'
import type { OperationScope } from '@/types/operations'

const props = defineProps<{ shop: number; scope: OperationScope }>()
const emit = defineEmits<{ loaded: [rule: BusinessRule]; pending: [value: boolean] }>()
const rule = ref<BusinessRule | null>(null)
const error = ref('')
let sequence = 0
async function load(): Promise<void> {
  const token = ++sequence
  rule.value = null
  error.value = ''
  emit('pending', true)
  if (!props.shop) return
  try {
    const value = await rulesApi.current(props.shop, props.scope.channel, props.scope.data_identity)
    if (sequence !== token) return
    rule.value = value
    emit('loaded', value)
    emit('pending', false)
  } catch (cause) {
    if (sequence === token) error.value = errorMessage(cause)
  }
}
watch(() => [props.shop, props.scope.channel, props.scope.data_identity], load, { immediate: true })
</script>
<template>
  <aside class="section-block" aria-label="本次经营规则">
    <details class="advanced-rules">
      <summary>
        高级选项 · 经营规则
        <span>{{ error ? '加载失败，请重试' : rule ? '已加载' : '正在加载…' }}</span>
      </summary>
      <div>
        <template v-if="rule">
          <strong>{{
            rule.active ? `经营规则 #${rule.version} 已应用` : '使用本次手填检查阈值'
          }}</strong>
          <p v-if="rule.active">
            库存 {{ rule.values.max_age_hours }} 小时内有效 · 最少 {{ rule.values.min_quantity }} 件
            · 低毛利阈值 {{ rule.values.max_margin_percent }}%。依据：{{ rule.values.basis }}
          </p>
          <p>生效范围：当前店铺、渠道和数据身份的今日运营与 Agent 检查。规则更新后须重新检查。</p>
          <RouterLink
            :to="{
              path: '/rules',
              query: {
                shop: props.shop,
                channel: props.scope.channel,
                identity: props.scope.data_identity,
              },
            }"
            >查看与修改经营规则</RouterLink
          >
        </template>
        <p v-else role="status">{{ error || '正在核对经营规则…' }}</p>
        <button type="button" class="button secondary small" @click="load">刷新规则</button>
      </div>
    </details>
  </aside>
</template>

<style scoped>
.advanced-rules summary {
  cursor: pointer;
  font-size: 0.9rem;
}
.advanced-rules summary span {
  color: var(--muted);
  font-size: 0.75rem;
  margin-left: 0.6rem;
}
.advanced-rules > div {
  padding: 1rem;
  margin-top: 0.75rem;
  background: #f1f4ef;
  border-radius: 8px;
}
</style>
