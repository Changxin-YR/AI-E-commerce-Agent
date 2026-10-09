<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { supportApi } from '@/api/support'
import { errorMessage } from '@/api/client'
import type { SupportContext, SupportWorkspace } from '@/types/support'
import SupportSource from './SupportSource.vue'

const props = defineProps<{
  shop: number
  message: number | null
  identity: string
  channel: string
  disabled: boolean
}>()
const emit = defineEmits<{ change: [context: SupportContext | null] }>()
const workspace = ref<SupportWorkspace | null>(null)
const selectedPolicies = ref<number[]>([])
const verified = ref(false)
const error = ref('')
const pending = ref(false)
let epoch = 0
async function load(): Promise<void> {
  const current = ++epoch
  workspace.value = null
  selectedPolicies.value = []
  verified.value = false
  emit('change', null)
  error.value = ''
  pending.value = false
  if (!props.shop || !props.message) return
  pending.value = true
  try {
    const value = await supportApi.workspace(props.shop, props.message)
    if (current !== epoch) return
    if (
      value.message.source.data_identity !== props.identity ||
      value.message.channel !== props.channel
    ) {
      error.value = '消息不属于当前数据身份或渠道，请重新选择。'
      return
    }
    workspace.value = value
  } catch (cause) {
    if (current === epoch) error.value = errorMessage(cause)
  } finally {
    if (current === epoch) pending.value = false
  }
}
watch(() => [props.shop, props.message, props.identity, props.channel], load, { immediate: true })
watch(
  [workspace, selectedPolicies, verified],
  () => {
    const value = workspace.value
    emit(
      'change',
      value && selectedPolicies.value.length <= 10
        ? {
            expected_source_row_id: value.message.source.row_id,
            expected_order_row_ids: verified.value ? value.orders.map((o) => o.source.row_id) : [],
            order_verified: verified.value,
            policy_ids: [...selectedPolicies.value],
          }
        : null,
    )
  },
  { deep: true },
)
onUnmounted(() => {
  epoch++
})
</script>

<template>
  <div class="data-note" aria-label="将发送的客服数据">
    <h3>核对本次客服数据</h3>
    <p v-if="pending">正在读取消息与政策…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="workspace">
      <p class="preserve-text">{{ workspace.message.body }}</p>
      <p>消息标注语言：{{ workspace.message.language }}</p>
      <SupportSource :shop-id="shop" :source="workspace.message.source" />
      <details v-if="workspace.orders.length">
        <summary>本地订单证据（{{ workspace.orders.length }} 行）</summary>
        <div v-for="order in workspace.orders" :key="order.source.row_id">
          <p>
            {{ order.order_id }} / {{ order.line_id }} · {{ order.sku }} · {{ order.status }} ·
            文件履约状态 {{ order.fulfillment_status }}
          </p>
          <SupportSource :shop-id="shop" :source="order.source" />
        </div>
      </details>
      <label v-if="workspace.orders.length" class="check-label">
        <input v-model="verified" type="checkbox" :disabled="disabled" />
        我已人工核验客户与上述全部当前订单行的关联
      </label>
      <p v-else>没有可核验的订单关联。订单号匹配不能证明买家身份。</p>
      <h4>选择允许发送的适用政策（最多 10 份）</h4>
      <p v-if="!workspace.policies.length">暂无适用政策，将保留人工核实提示。</p>
      <article v-for="policy in workspace.policies" :key="policy.id" class="support-policy-quote">
        <label class="check-label">
          <input
            v-model="selectedPolicies"
            type="checkbox"
            :value="policy.id"
            :disabled="disabled"
          />
          {{ policy.data?.title }} · v{{ policy.number }}
        </label>
        <p>
          出处：{{ policy.data?.source }} · 来源版本 {{ policy.data?.source_version }} ·
          {{ policy.data?.source_confirmed ? '卖家已核对' : '出处待核对' }}
        </p>
        <p class="preserve-text">{{ policy.data?.text }}</p>
      </article>
      <p v-if="selectedPolicies.length > 10" role="alert">请最多选择 10 份政策。</p>
    </template>
    <p v-else-if="!pending && !error">请先选择目标消息。</p>
    <p>
      一次模型请求将发送目标、上述消息原文及语言、选中政策的主题/全文/核对状态，以及订单关联是否经过人工核验。原文若含姓名、邮箱、地址或订单号，也会随正文发送，请先核对。结构化订单号、SKU、文件名和政策出处留在本地。
    </p>
    <p>
      模型返回意图、事实与政策编号。本地规则保留敏感诉求和物流缺口，结果由人工审阅后保存为草稿。
    </p>
    <button
      class="button secondary small"
      type="button"
      :disabled="disabled || pending"
      @click="load"
    >
      刷新客服依据
    </button>
  </div>
</template>

<style scoped>
.data-note {
  overflow-wrap: anywhere;
}
input[type='checkbox'] {
  width: 18px;
  height: 18px;
  margin-right: 8px;
}
</style>
