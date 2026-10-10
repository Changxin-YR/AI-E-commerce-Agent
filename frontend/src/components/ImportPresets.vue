<script setup lang="ts">
import type { ImportPreset } from '@/types/imports'

defineProps<{ presets: ImportPreset[]; disabled: boolean }>()
const emit = defineEmits<{ apply: [id: string] }>()
const fieldLabels: Record<string, string> = {
  sku: 'SKU',
  name: '商品名',
  price: '销售单价',
  unit_cost: '单位采购成本',
}
</script>
<template>
  <section v-if="presets.length" class="section-block preset-panel" aria-label="渠道字段预设">
    <h4>经核实的字段候选</h4>
    <article v-for="preset in presets" :key="preset.id">
      <p>{{ preset.name }}</p>
      <p class="muted">
        官方字段核实日期 {{ preset.verified_on }} ·
        <a :href="preset.reference_url" target="_blank" rel="noopener noreferrer">官方格式依据</a>
      </p>
      <p class="muted">
        {{
          Object.entries(preset.mapping)
            .map(([field, column]) => `${column} → ${fieldLabels[field] ?? field}`)
            .join('；')
        }}
      </p>
      <ul>
        <li v-for="note in preset.notes" :key="note">{{ note }}</li>
      </ul>
      <button class="button secondary" :disabled="disabled" @click="emit('apply', preset.id)">
        应用此候选映射
      </button>
    </article>
  </section>
</template>
<style scoped>
.preset-panel {
  min-width: 0;
  border: 1px solid var(--line);
  padding: 16px;
  overflow-wrap: anywhere;
}
.preset-panel li {
  margin-block: 8px;
}
</style>
