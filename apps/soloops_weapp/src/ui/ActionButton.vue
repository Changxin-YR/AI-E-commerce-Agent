<template>
  <button
    class="action"
    :class="[`action--${variant}`, { 'action--block': block }]"
    :disabled="disabled || loading"
    :loading="loading"
    size="mini"
    @tap="emit('tap')"
  >
    {{ label }}
  </button>
</template>

<script setup lang="ts">
/**
 * ActionButton：统一动作按钮。busy 时禁用，避免重复提交造成二次写入。
 */
withDefaults(
  defineProps<{
    label: string
    variant?: 'primary' | 'secondary' | 'ghost'
    block?: boolean
    disabled?: boolean
    loading?: boolean
  }>(),
  { variant: 'secondary', block: false, disabled: false, loading: false },
)

const emit = defineEmits<{ (event: 'tap'): void }>()
</script>
