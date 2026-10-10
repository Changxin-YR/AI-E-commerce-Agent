<script setup lang="ts">
import { computed } from 'vue'
import BusinessDateTime from './BusinessDateTime.vue'
import { exactTimeError, localTime } from '@/composables/businessTime'
const props = defineProps<{
  start: string
  end: string
  timezone: string
  startLabel: string
  endLabel: string
  fixedDays?: number
}>()
const emit = defineEmits<{ 'update:start': [value: string]; 'update:end': [value: string] }>()
const actualStart = computed(() =>
  props.fixedDays && Number.isFinite(Date.parse(props.end))
    ? new Date(Date.parse(props.end) - props.fixedDays * 86400000).toISOString()
    : props.start,
)
const summary = computed(() => {
  if (
    !actualStart.value ||
    !props.end ||
    exactTimeError(actualStart.value, props.timezone) ||
    exactTimeError(props.end, props.timezone)
  )
    return '请补全有效时间范围。'
  if (Date.parse(actualStart.value) >= Date.parse(props.end)) return '起点必须早于终点。'
  return `${localTime(actualStart.value, props.timezone).replace('T', ' ')} 至 ${localTime(props.end, props.timezone).replace('T', ' ')} · ${props.timezone}（计入起点，不计入终点）`
})
function recent(days: number): void {
  const now = Date.now()
  emit('update:start', new Date(now - days * 86400000).toISOString())
  emit('update:end', new Date(now).toISOString())
}
</script>
<template>
  <div class="full-width">
    <div class="button-row">
      <button
        v-for="days in fixedDays ? [fixedDays] : [7, 30]"
        :key="days"
        type="button"
        class="button secondary small"
        @click="recent(days)"
      >
        最近 {{ days }} 天
      </button>
      <small>从当前时刻回溯，每天 24 小时。</small>
    </div>
    <div class="form-grid">
      <BusinessDateTime
        v-if="!fixedDays"
        :model-value="start"
        :timezone="timezone"
        :label="startLabel"
        required
        @update:model-value="emit('update:start', $event)"
      />
      <BusinessDateTime
        :model-value="end"
        :timezone="timezone"
        :label="endLabel"
        required
        @update:model-value="emit('update:end', $event)"
      />
    </div>
    <p aria-label="本次时间范围">{{ summary }}</p>
  </div>
</template>
