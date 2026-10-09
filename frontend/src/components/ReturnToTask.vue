<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { linkedId, applyLinkedScope, scopeQuery } from '@/composables/deepLink'
import type { AnalysisScope } from '@/types/analytics'

const route = useRoute()
const destination = computed(() => {
  try {
    const task = linkedId(route.query.return_task)
    const shop = linkedId(route.query.shop)
    if (!task || !shop) return null
    const scope: Partial<AnalysisScope> = {}
    applyLinkedScope(scope, route.query)
    return { path: '/', query: { shop, task, ...scopeQuery(scope) }, hash: '#linked-task' }
  } catch {
    return null
  }
})
</script>

<template>
  <p v-if="destination" class="data-note" aria-label="关联运营事项">
    <RouterLink :to="destination">返回原运营事项 #{{ destination.query.task }}</RouterLink>
    <span> · 保存本页结果后，可回到原事项记录核对结论。</span>
  </p>
</template>
