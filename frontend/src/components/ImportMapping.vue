<script setup lang="ts">
import type { FieldDefinition, ImportBatch } from '@/types/imports'

defineProps<{
  batch: ImportBatch
  fields: FieldDefinition[]
  mapping: Record<string, string>
  disabled: boolean
}>()
const emit = defineEmits<{ change: [field: string, column: string] }>()
</script>
<template>
  <div class="mapping-grid">
    <div v-for="field in fields" :key="field.key" class="mapping-field">
      <label :for="`map-${field.key}`"
        >{{ field.label }} <span v-if="field.required">*</span></label
      >
      <small>{{ field.data_type }} · {{ field.help }}</small>
      <select
        :id="`map-${field.key}`"
        :value="mapping[field.key] || ''"
        :disabled="disabled"
        @change="emit('change', field.key, ($event.target as HTMLSelectElement).value)"
      >
        <option value="">不映射</option>
        <option v-for="column in batch.headers" :key="column" :value="column">{{ column }}</option>
      </select>
      <small v-if="mapping[field.key]"
        >原始示例：{{ batch.examples[mapping[field.key]!] || '空值' }}</small
      >
      <small
        v-if="
          batch.suggestions.some(
            (item) => item.field === field.key && item.column === mapping[field.key],
          )
        "
      >
        {{
          batch.suggestions.find((item) => item.field === field.key)?.confidence === 'exact'
            ? '标准字段匹配'
            : '别名候选，请核对口径'
        }}
      </small>
    </div>
  </div>
</template>
