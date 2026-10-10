<script setup lang="ts">
import type { MappingReview } from '@/types/imports'

defineProps<{ reviews: MappingReview[]; disabled: boolean }>()
const reviewed = defineModel<string[]>({ required: true })
</script>
<template>
  <fieldset v-if="reviews.length" class="section-block meaning-review" :disabled="disabled">
    <legend>确认关键字段含义</legend>
    <p class="muted">
      根据原报表说明核对这些映射。金额含义或稳定标识无法确认时，请先纠错；整单退款不能直接当作行退款。
      个人模板只保存映射，每次导入仍需核对。
    </p>
    <label v-for="review in reviews" :key="review.field" class="check-label section-block">
      <input v-model="reviewed" type="checkbox" :value="review.field" />
      <span>已核对 {{ review.column }} → {{ review.label }}：{{ review.meaning }}</span>
    </label>
  </fieldset>
</template>
<style scoped>
.meaning-review {
  min-width: 0;
  border: 1px solid var(--line);
}
.meaning-review span {
  overflow-wrap: anywhere;
}
</style>
