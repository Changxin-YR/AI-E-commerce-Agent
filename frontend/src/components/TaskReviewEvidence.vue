<script setup lang="ts">
import type { TaskReview } from '@/types/operations'
import { businessLabels } from '@/types/operations'
import { supportTime } from '@/types/support'
import SourceEvidence from './SupportSource.vue'

defineProps<{ review: TaskReview; shopId: number; timezone: string }>()
</script>

<template>
  <div class="review-evidence">
    <div v-if="review.evidence">
      <p><strong>卖家自报操作：</strong>{{ review.evidence.description }}</p>
      <p>依据：{{ review.evidence.evidence_ref }}</p>
      <p>
        发生于 {{ supportTime(review.evidence.occurred_at, timezone) }}；卖家 #{{
          review.evidence.recorded_by
        }}
        登记于 {{ supportTime(review.evidence.recorded_at, timezone) }}。
      </p>
    </div>
    <div v-if="review.recheck">
      <p><strong>存档复检结论：</strong>{{ businessLabels[review.recheck.state] }}</p>
      <p>{{ review.recheck.reason }}</p>
      <p>
        复检于 {{ supportTime(review.recheck.checked_at, timezone) }} · 来源版本
        {{ review.recheck.source_revision }}
      </p>
      <p v-if="review.recheck.valid_until">
        有效至 {{ supportTime(review.recheck.valid_until, timezone) }}
      </p>
      <details>
        <summary>复检事实与来源（{{ review.recheck.sources.length }} 行）</summary>
        <dl>
          <template v-for="(value, label) in review.recheck.facts" :key="label"
            ><dt>{{ label }}</dt>
            <dd>{{ value }}</dd></template
          >
        </dl>
        <SourceEvidence
          v-for="source in review.recheck.sources"
          :key="source.row_id"
          :shop-id="shopId"
          :source="source"
        />
      </details>
    </div>
  </div>
</template>

<style scoped>
.review-evidence {
  overflow-wrap: anywhere;
}
dl {
  display: grid;
  grid-template-columns: minmax(5rem, 1fr) 3fr;
  gap: 0.5rem;
}
dd {
  margin: 0;
  min-width: 0;
}
</style>
