<script setup lang="ts">
import type { OperationTask } from '@/types/operations'
import SupportSource from './SupportSource.vue'
defineProps<{ finding: NonNullable<OperationTask['snapshot']>; shop: number }>()
</script>
<template>
  <article class="analysis-line">
    <strong>{{ finding.title }} · {{ finding.object_label }}</strong>
    <p>{{ finding.basis }}</p>
    <p>{{ finding.advice }}</p>
    <p>{{ finding.impact }}</p>
    <details>
      <summary>核对候选事实与 {{ finding.sources.length }} 行来源</summary>
      <dl>
        <template v-for="(value, key) in finding.facts" :key="key">
          <dt>{{ key }}</dt>
          <dd>{{ value }}</dd>
        </template>
      </dl>
      <SupportSource
        v-for="source in finding.sources"
        :key="source.row_id"
        :shop-id="shop"
        :source="source"
      />
    </details>
  </article>
</template>
