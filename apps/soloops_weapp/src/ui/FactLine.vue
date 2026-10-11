<template>
  <view class="fact">
    <text class="fact__label">{{ label }}</text>
    <text class="fact__sep">：</text>
    <text class="fact__value" :class="{ 'fact__value--unknown': unknown }">{{ rendered }}</text>
  </view>
</template>

<script setup lang="ts">
/**
 * FactLine：字段名 + 值。未知值显示“未知”，不显示 0 或猜测值。
 * 文本中的 UTC 时间按传入的业务时区展示。
 */
import { computed } from 'vue'
import { UNKNOWN_TEXT, businessTimeText, factText } from '../core/format'

const props = withDefaults(
  defineProps<{
    label: string
    value?: unknown
    /** 业务时区（IANA）；缺省时时间按原值展示并标注“（原始时间）”。 */
    zone?: string
  }>(),
  { zone: 'UTC' },
)

const unknown = computed(
  () => props.value === null || props.value === undefined || `${props.value}`.trim() === '',
)

const rendered = computed(() => {
  if (unknown.value) return UNKNOWN_TEXT
  if (typeof props.value === 'string' || typeof props.value === 'number') {
    return businessTimeText(props.value, props.zone)
  }
  return factText(props.value)
})
</script>
