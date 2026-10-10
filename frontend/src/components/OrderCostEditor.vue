<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { analyticsApi } from '@/api/analytics'
import { errorMessage } from '@/api/client'
import type { CostHistory, CostWrite } from '@/types/analytics'
import FeedbackBanner from './FeedbackBanner.vue'

const props = defineProps<{ shopId: number; rowId: number; timezone: string; disabled?: boolean }>()
const emit = defineEmits<{ changed: []; working: [boolean] }>()
const page = ref<CostHistory | null>(null)
const busy = ref(false)
const error = ref('')
const message = ref('')
const confirmed = ref(false)
const draft = reactive({ unit_cost: '', currency: '', evidence_ref: '', evidence_at: '' })
watch(draft, () => {
  confirmed.value = false
})
let pending: { fingerprint: string; data: CostWrite } | null = null
const states: Record<string, string> = {
  active: '当前有效',
  superseded: '已被新版本替代',
  stale: '来源变化待重核',
  revoked: '已撤销',
  cleared: '内容已清除',
}
watch(
  () => [props.shopId, props.rowId],
  () => {
    page.value = null
    pending = null
    confirmed.value = false
  },
)
function time(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: props.timezone,
    dateStyle: 'medium',
    timeStyle: 'long',
  }).format(new Date(value))
}
async function load(): Promise<void> {
  busy.value = true
  error.value = ''
  message.value = ''
  page.value = null
  const shop = props.shopId,
    row = props.rowId
  try {
    const result = await analyticsApi.costHistory(shop, row)
    if (shop !== props.shopId || row !== props.rowId) return
    page.value = result
    const latest = result.history[0]
    draft.unit_cost = latest?.unit_cost ?? ''
    draft.currency = latest?.currency ?? ''
    draft.evidence_ref = latest?.evidence_ref ?? ''
    draft.evidence_at = latest?.evidence_at ?? ''
    confirmed.value = false
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function save(action: 'upsert' | 'revoke'): Promise<void> {
  if (!page.value || !confirmed.value || props.disabled || busy.value) return
  const body = {
    expected_version: page.value.version,
    expected_revision: page.value.source_revision,
    action,
    ...(action === 'upsert' ? { content: { ...draft, confirmed: true } } : {}),
  }
  const fingerprint = JSON.stringify(body)
  if (pending?.fingerprint !== fingerprint)
    pending = { fingerprint, data: { ...body, request_id: crypto.randomUUID() } }
  busy.value = true
  emit('working', true)
  error.value = ''
  const shop = props.shopId,
    row = props.rowId
  try {
    const saved = await analyticsApi.writeCost(shop, row, pending.data)
    if (shop !== props.shopId || row !== props.rowId) return
    page.value = saved
    pending = null
    confirmed.value = false
    message.value = '成本凭据操作已保存。请重新计算，旧分析保留原口径。'
    emit('changed')
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
    emit('working', false)
  }
}
</script>
<template>
  <div class="order-cost-editor">
    <button type="button" class="button secondary small" :disabled="busy" @click="load">
      历史成本凭据与版本
    </button>
    <FeedbackBanner :message="error" />
    <FeedbackBanner :message="message" kind="success" />
    <section v-if="page" aria-label="订单行历史成本凭据" class="source-detail">
      <h3>{{ page.order_id }} / {{ page.line_id }} · {{ page.sku }} · 历史单位成本</h3>
      <p>
        批次 {{ page.source_batch_id }} · {{ page.channel }} ·
        {{ page.data_identity === 'synthetic' ? '合成测试数据' : '用户导入数据' }} · 订单币种
        {{ page.currency }}
      </p>
      <p>
        仅填写此订单行的历史单位采购成本。凭据为卖家提供并确认，系统未独立核验；缺依据请保留未知。异币种不自动换算，退款不恢复采购成本。
      </p>
      <p v-if="!page.source_current" role="alert">
        此订单来源已变化或撤销。请重新计算并定位当前源行后录入。
      </p>
      <p v-else-if="disabled">请重新计算后再修改成本凭据。</p>
      <form v-if="page.source_current" @submit.prevent="save('upsert')">
        <fieldset :disabled="busy || disabled" class="analysis-fields">
          <label
            >历史单位采购成本<input
              v-model="draft.unit_cost"
              type="text"
              inputmode="decimal"
              pattern="[0-9]+([.][0-9]{1,4})?"
              maxlength="19"
              required
          /></label>
          <label
            >凭据币种<select v-model="draft.currency" required>
              <option value="" disabled>按凭据选择</option>
              <option
                v-for="currency in ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']"
                :key="currency"
              >
                {{ currency }}
              </option>
            </select></label
          >
          <label class="full-width"
            >凭据来源与说明<input
              v-model="draft.evidence_ref"
              maxlength="500"
              required
              placeholder="采购凭据编号及适用此订单行的依据"
          /></label>
          <label class="full-width"
            >凭据时间（含时区）<input
              v-model="draft.evidence_at"
              required
              placeholder="2026-10-06T08:00:00+08:00"
          /></label>
          <label class="check-label full-width"
            ><input
              v-model="confirmed"
              type="checkbox"
            />我已核对订单行、金额、币种和凭据，确认本次保存或撤销</label
          >
          <div class="button-row full-width">
            <button type="submit" class="button primary small" :disabled="!confirmed">
              确认保存成本凭据
            </button>
            <button
              v-if="page.history.length && page.history[0]?.status !== 'revoked'"
              type="button"
              class="button secondary small"
              :disabled="!confirmed"
              @click="save('revoke')"
            >
              撤销当前成本凭据
            </button>
          </div>
        </fieldset>
      </form>
      <p v-if="!page.history.length">尚无历史成本凭据，历史模式显示未知。</p>
      <details v-for="item in page.history" :key="item.id" class="analysis-line">
        <summary>成本版本 {{ item.version }} · {{ states[item.status] ?? item.status }}</summary>
        <p>
          单位成本 {{ item.unit_cost ?? '未知 / 已撤销' }} {{ item.currency }} ·
          {{ item.evidence_ref }}
        </p>
        <p>
          凭据时间：{{ item.evidence_at ? time(item.evidence_at) : '无' }}；操作时间：{{
            time(item.recorded_at)
          }}
        </p>
      </details>
    </section>
  </div>
</template>
