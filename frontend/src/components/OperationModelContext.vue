<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { operationsApi } from '@/api/operations'
import { errorMessage } from '@/api/client'
import type { OperationContext, OperationScope } from '@/types/operations'

const props = defineProps<{ shop: number; scope: OperationScope; disabled: boolean }>()
const emit = defineEmits<{ change: [hash: string | null] }>()
const context = ref<OperationContext | null>(null)
const error = ref('')
const pending = ref(false)
let epoch = 0
const labels: Record<string, string> = {
  order_review: '履约核对',
  low_inventory: '低库存核对',
  message_review: '消息回复核对',
  low_margin: '低毛利核对',
}
const counts = computed(() =>
  Object.entries(labels).map(([kind, label]) => ({
    kind,
    label,
    count: context.value?.preview.findings.filter((f) => f.kind === kind).length ?? 0,
  })),
)
async function load(): Promise<void> {
  const current = ++epoch
  context.value = null
  error.value = ''
  emit('change', null)
  pending.value = true
  try {
    const value = await operationsApi.preview(props.shop, props.scope)
    if (current !== epoch) return
    context.value = value
    emit('change', value.preview_hash)
  } catch (cause) {
    if (current === epoch) error.value = errorMessage(cause)
  } finally {
    if (current === epoch) pending.value = false
  }
}
watch(() => [props.shop, JSON.stringify(props.scope)], load, { immediate: true })
onUnmounted(() => {
  epoch++
})
</script>

<template>
  <section class="data-note" aria-label="将发送的运营数据">
    <h3>核对本次运营数据</h3>
    <p>
      一次模型请求发送目标原文、表单范围、下列分支名称/状态/行数和四类候选数量。目标原文请自行核对；订单号、SKU、消息正文、文件名和具体事实留在本地。
    </p>
    <p>
      模型安排概览顺序与核对建议；全部分支、缺失项和候选会保留。文件数据不能证明平台当前状态，已知毛利不能当作净利润。
    </p>
    <p v-if="pending">正在核对来源…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="context">
      <p>本地来源版本 {{ context.preview.source_revision }}</p>
      <ul>
        <li v-for="branch in context.preview.branches" :key="branch.name">
          {{ branch.name }} ·
          {{ { checked: '已检查', partial: '部分检查', not_checked: '未检查' }[branch.status] }} ·
          {{ branch.count }} 行
        </li>
      </ul>
      <p v-for="item in counts" :key="item.kind">{{ item.label }}：{{ item.count }} 项</p>
    </template>
    <button type="button" class="button secondary" :disabled="disabled || pending" @click="load">
      刷新运营数据
    </button>
  </section>
</template>
<style scoped>
.data-note {
  display: block;
  min-width: 0;
  overflow-wrap: anywhere;
}
</style>
