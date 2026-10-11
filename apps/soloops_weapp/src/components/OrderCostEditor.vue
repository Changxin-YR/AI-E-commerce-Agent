<script setup lang="ts">
import { onBeforeUnmount, reactive, ref, watch } from 'vue'
import Taro from '@tarojs/taro'
import { account, api } from '../services/session'
import { ApiError } from '../services/client'
import { scopedRequest } from '../services/scoped-request'
import { requestId } from '../services/task-policy'
import { costWrite } from '../services/analytics-policy'
import { supportTime } from '../services/support-types'
import type { CostHistory, CostWrite } from '../services/analytics-types'
const props = defineProps<{
  row: number
  timezone: string
  disabled: boolean
}>()
const emit = defineEmits<{
  changed: []
  working: [boolean]
  editing: [boolean]
}>()
const page = ref<CostHistory>(),
  busy = ref(false),
  error = ref(''),
  pending = ref<CostWrite>(),
  editing = ref(false),
  notice = ref('')
const form = reactive({
  unit_cost: '',
  currency: '',
  evidence_ref: '',
  evidence_at: '',
  confirmed: false,
})
let alive = true
const request = scopedRequest(api, () =>
  alive
    ? `${account.shopId}:${account.session?.session_id}:${props.row}`
    : null,
)
const base = () => `/shops/${account.shopId}/analytics/order-costs/${props.row}`
onBeforeUnmount(() => {
  alive = false
})
watch(
  () => [form.unit_cost, form.currency, form.evidence_ref, form.evidence_at],
  () => {
    form.confirmed = false
  },
  { flush: 'sync' },
)
watch(editing, (value) => emit('editing', value), { flush: 'sync' })
async function run(work: () => Promise<void>) {
  if (busy.value || !alive || props.disabled) return
  busy.value = true
  emit('working', true)
  error.value = ''
  try {
    await work()
  } catch (cause) {
    if (alive)
      error.value = cause instanceof Error ? cause.message : '成本操作失败。'
  } finally {
    busy.value = false
    if (alive) emit('working', false)
  }
}
async function load() {
  await run(async () => {
    if (pending.value) throw new Error('请先按原请求恢复待核对的成本操作。')
    if (editing.value) {
      const answer = await Taro.showModal({
        title: '重新读取成本',
        content: '是否放弃未保存的成本表单？',
      })
      if (!answer.confirm || !alive) return
    }
    page.value = await request<CostHistory>(base())
    const latest = page.value.history[0]
    Object.assign(form, {
      unit_cost: latest?.unit_cost || '',
      currency: latest?.currency || page.value.currency,
      evidence_ref: latest?.evidence_ref || '',
      evidence_at: latest?.evidence_at || '',
      confirmed: false,
    })
    editing.value = true
  })
}
async function close() {
  if (busy.value || pending.value) return
  const answer = await Taro.showModal({
    title: '关闭成本编辑',
    content: '放弃尚未保存的表单内容？',
  })
  if (answer.confirm && alive) {
    page.value = undefined
    editing.value = false
  }
}
async function save(action: 'upsert' | 'revoke') {
  await run(async () => {
    if (!page.value) return
    pending.value ||= costWrite(page.value, action, { ...form }, requestId())
    try {
      await request<CostHistory>(base(), 'POST', pending.value)
    } catch (cause) {
      if (
        cause instanceof ApiError &&
        cause.status >= 400 &&
        cause.status < 500
      )
        pending.value = undefined
      throw cause
    }
    page.value = await request<CostHistory>(base())
    pending.value = undefined
    form.confirmed = false
    editing.value = false
    notice.value = '成本凭据已保存并回读，请重新计算分析。'
    emit('changed')
  })
}
function confirm(event: unknown) {
  form.confirmed = Boolean(
    (event as { detail: { value: boolean } }).detail.value,
  )
}
</script>
<template>
  <view>
    <button :disabled="busy || disabled || !!pending" @tap="load">
      历史单位成本与凭据版本
    </button>
    <text v-if="error" class="error">{{ error }}</text
    ><text v-if="notice" class="hint">{{ notice }}</text>
    <view v-if="page" class="card">
      <text class="label"
        >{{ page.order_id }} / {{ page.line_id }} · {{ page.sku }}</text
      >
      <text class="hint"
        >批次 #{{ page.source_batch_id }} · {{ page.channel }} /
        {{ page.data_identity }} · 订单币种 {{ page.currency }}</text
      >
      <text class="hint"
        >卖家确认的历史单位采购成本；系统未独立核验，异币种不自动换算，退款不恢复成本。</text
      >
      <text v-if="!page.source_current" class="error"
        >订单来源已变化，请重新计算并定位当前源行。</text
      >
      <template v-if="page.source_current && editing">
        <text class="label">历史单位采购成本</text
        ><input
          v-model="form.unit_cost"
          :maxlength="19"
          :disabled="busy || disabled || !!pending"
        />
        <text class="label">凭据币种</text
        ><input
          v-model="form.currency"
          :maxlength="3"
          :disabled="busy || disabled || !!pending"
        />
        <text class="label">凭据来源与说明</text
        ><input
          v-model="form.evidence_ref"
          :maxlength="500"
          :disabled="busy || disabled || !!pending"
        />
        <text class="label">凭据时间（含时区）</text
        ><input
          v-model="form.evidence_at"
          placeholder="2026-10-11T09:00:00+08:00"
          :maxlength="40"
          :disabled="busy || disabled || !!pending"
        />
        <view class="row"
          ><text>已核对订单行、成本、币种和凭据</text
          ><switch
            :checked="form.confirmed"
            :disabled="busy || disabled || !!pending"
            @change="confirm"
        /></view>
        <button
          :disabled="busy || disabled || (!pending && !form.confirmed)"
          @tap="save('upsert')"
        >
          {{ pending ? '恢复原成本操作并回读' : '保存成本凭据' }}
        </button>
        <button
          v-if="page.history.length && page.history[0]?.status !== 'revoked'"
          :disabled="busy || disabled || !!pending || !form.confirmed"
          @tap="save('revoke')"
        >
          撤销当前成本凭据
        </button>
      </template>
      <button :disabled="busy || !!pending" @tap="close">关闭成本编辑</button>
      <text v-if="!page.history.length" class="muted"
        >尚无历史成本凭据，历史模式为未知。</text
      >
      <view v-for="item in page.history" :key="item.id"
        ><text
          >v{{ item.version }} · {{ item.status }} ·
          {{ item.unit_cost ?? '未知或已撤销' }} {{ item.currency }}</text
        ><text>{{ item.evidence_ref }}</text
        ><text class="hint"
          >凭据
          {{
            item.evidence_at ? supportTime(item.evidence_at, timezone) : '无'
          }}
          · 操作 {{ supportTime(item.recorded_at, timezone) }}</text
        ></view
      >
    </view>
  </view>
</template>
