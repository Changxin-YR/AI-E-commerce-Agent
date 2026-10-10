<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { exactTimeError, localTime, resolveLocalTime } from '@/composables/businessTime'
const props = defineProps<{
  modelValue: string | null
  timezone: string
  label: string
  required?: boolean
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const id = useId()
const native = ref<HTMLInputElement>()
const exact = ref<HTMLInputElement>()
const display = ref('')
const error = ref('')
const advanced = ref(false)
let localIssue = false
const preview = computed(() => {
  try {
    return props.modelValue
      ? `${localTime(props.modelValue, props.timezone).replace('T', ' ')} · ${props.timezone}`
      : '待选择'
  } catch {
    return '待核对时间与时区'
  }
})
watch(
  () => [props.modelValue, props.timezone],
  () => {
    if (localIssue && props.modelValue === 'invalid-local-time') return
    localIssue = false
    error.value = exactTimeError(props.modelValue ?? '', props.timezone)
    try {
      display.value = error.value ? '' : localTime(props.modelValue ?? '', props.timezone)
    } catch {
      error.value = '请填写有效的 IANA 业务时区。'
    }
  },
  { immediate: true },
)
watch(
  [error, native, exact, advanced],
  () => {
    native.value?.setCustomValidity(advanced.value ? '' : error.value)
    exact.value?.setCustomValidity(advanced.value ? error.value : '')
  },
  { flush: 'post' },
)
function select(value: string): void {
  display.value = value
  localIssue = false
  try {
    const instant = resolveLocalTime(value, props.timezone)
    error.value = ''
    emit('update:modelValue', instant)
  } catch (cause) {
    // Keep invalid local input visible and prevent form submission. Never reuse
    // the last valid instant after a failed edit.
    localIssue = true
    emit('update:modelValue', 'invalid-local-time')
    error.value = cause instanceof Error ? cause.message : '请核对时间与时区。'
  }
}
function inputExact(value: string): void {
  localIssue = false
  error.value = exactTimeError(value, props.timezone)
  emit('update:modelValue', value)
}
</script>
<template>
  <div class="form-field business-time">
    <label :for="`${id}-local`">选择{{ label.replace(/（.*?）/g, '') }}日期和时间</label>
    <input
      :id="`${id}-local`"
      ref="native"
      type="datetime-local"
      step="1"
      :value="display"
      :required="required && !advanced"
      :disabled="disabled || advanced"
      @input="select(($event.target as HTMLInputElement).value)"
    />
    <small>业务时区 {{ timezone }}；当前选择：{{ preview }}</small>
    <details @toggle="advanced = ($event.target as HTMLDetailsElement).open">
      <summary>高级：精确 ISO 时间</summary>
      <label :for="`${id}-exact`">{{ label }}</label>
      <input
        :id="`${id}-exact`"
        ref="exact"
        :value="modelValue ?? ''"
        :required="required && advanced"
        :disabled="disabled || !advanced"
        placeholder="2026-10-10T08:00:00+08:00"
        @input="inputExact(($event.target as HTMLInputElement).value)"
      />
    </details>
    <small v-if="error" role="alert">{{ error }}</small>
  </div>
</template>
<style scoped>
.business-time {
  min-width: 0;
}
input {
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}
small {
  overflow-wrap: anywhere;
}
</style>
