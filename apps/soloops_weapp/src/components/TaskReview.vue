<script setup lang="ts">
import type { TaskReview } from '../services/operation-types'
import { businessLabels } from '../services/operation-types'
import SourceList from './SourceList.vue'
defineProps<{ review: TaskReview; shopId: number; current?: boolean }>()
</script>
<template>
  <view>
    <text class="label">{{
      businessLabels[review.state] || review.state
    }}</text>
    <text v-if="current === false && review.recheck" class="error"
      >存档结论已失效，请更新来源后重新复检。</text
    >
    <view v-if="review.evidence"
      ><text class="hint">卖家自报：{{ review.evidence.description }}</text
      ><text class="hint"
        >凭据 {{ review.evidence.evidence_ref }} · 操作
        {{ review.evidence.occurred_at }} · 登记
        {{ review.evidence.recorded_at }}</text
      ><text class="hint">此记录不等于渠道确认或买家收件。</text></view
    >
    <view v-if="review.recheck"
      ><text class="hint">{{ review.recheck.reason }}</text
      ><text class="hint"
        >复检 {{ review.recheck.checked_at }} · 来源修订
        {{ review.recheck.source_revision }} · 有效至
        {{ review.recheck.valid_until || '未知' }}</text
      ><text
        v-for="(value, key) in review.recheck.facts"
        :key="key"
        class="hint"
        >{{ key }}：{{ value }}</text
      ><SourceList :sources="review.recheck.sources" :shop-id="shopId"
    /></view>
  </view>
</template>
