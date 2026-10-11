<script setup lang="ts">
import { ref, watch } from 'vue'
import { account, api } from '../services/session'
import { queryString } from '../services/task-policy'
import type { OperationScope } from '../services/operation-types'
const props = defineProps<{ scope: OperationScope; disabled: boolean }>()
const emit = defineEmits<{
  pending: [boolean]
  loaded: [
    {
      version: number
      active: boolean
      values: {
        max_age_hours: number
        min_quantity: number
        max_margin_percent: string
        basis: string
      }
    },
  ]
}>()
const rule = ref<{
  version: number
  active: boolean
  values: {
    max_age_hours: number
    min_quantity: number
    max_margin_percent: string
    basis: string
  }
}>()
const error = ref(''),
  loading = ref(false)
let sequence = 0
async function load() {
  const token = ++sequence
  rule.value = undefined
  error.value = ''
  loading.value = true
  emit('pending', true)
  if (!account.shopId) {
    loading.value = false
    return
  }
  try {
    const value = await api.request<NonNullable<typeof rule.value>>(
      `/shops/${account.shopId}/business-rules?${queryString({ channel: props.scope.channel, data_identity: props.scope.data_identity })}`,
    )
    if (token !== sequence) return
    rule.value = value
    emit('loaded', value)
    emit('pending', false)
  } catch (cause) {
    if (token === sequence)
      error.value = cause instanceof Error ? cause.message : '规则读取失败'
  } finally {
    if (token === sequence) loading.value = false
  }
}
watch(
  () => [
    account.shopId,
    account.session?.session_id,
    props.scope.channel,
    props.scope.data_identity,
  ],
  load,
  { immediate: true },
)
</script>
<template>
  <view
    ><text class="label">经营规则</text
    ><text v-if="rule" class="hint"
      >规则 #{{ rule.version }} · {{ rule.active ? '已应用' : '手填阈值' }} ·
      {{ rule.values.basis }}</text
    ><text v-if="error" class="error">{{ error }}</text
    ><button :disabled="disabled || loading" @tap="load">
      刷新规则依据
    </button></view
  >
</template>
