<script setup lang="ts">
import type { MarginEvidence } from '@/types/agent'
import { supportTime } from '@/types/support'
defineProps<{ value: MarginEvidence }>()
</script>

<template>
  <section class="margin-evidence data-note" aria-label="低毛利复核依据与建议">
    <h3>最近7天 · 依据与下一步</h3>
    <p>
      {{ supportTime(value.scope.start_at, value.scope.timezone) }} 至
      {{ supportTime(value.scope.end_at, value.scope.timezone) }}（结束不含，{{
        value.scope.timezone
      }}）
    </p>
    <p>
      {{ value.scope.data_identity }} · {{ value.scope.channel }} · {{ value.scope.currency }} ·
      来源版本 {{ value.source_revision }}
    </p>
    <p>{{ value.cost_basis }}</p>
    <p>
      {{ value.included_lines }} 条符合口径订单行；{{
        value.ranking_available
          ? `低毛利命中 ${value.candidate_count} 个 SKU`
          : '数据不足，完整毛利排行不可用'
      }}。
    </p>
    <p v-if="value.candidates.length">
      {{ value.candidates.join('、')
      }}<span v-if="value.candidate_count > value.candidates.length"
        >（此处最多显示 {{ value.candidate_limit }} 项，完整结果见下方分析）</span
      >
    </p>
    <ul v-if="value.data_gaps.length">
      <li v-for="gap in value.data_gaps" :key="gap">{{ gap }}</li>
    </ul>
    <p>费用待核：{{ value.fee_gaps.join('、') }}。商品毛利未扣完整费用，尚无法核实净利润。</p>
    <article v-for="item in value.recommendations" :key="item.kind">
      <h4>{{ item.title }} · {{ item.risk }}</h4>
      <p>{{ item.evidence }}</p>
      <p>{{ item.action }}</p>
    </article>
    <p>{{ value.listing_note }}</p>
    <details v-if="value.listing">
      <summary>核对本地版本 #{{ value.listing.active_id }} 的参数遗漏</summary>
      <p>商品：{{ value.listing.product.sku }} · {{ value.listing.product.name }}</p>
      <p>来源中存在、当前本地版本遗漏的完整参数：</p>
      <ul>
        <li v-for="parameter in value.listing.missing_parameters" :key="parameter">
          {{ parameter }}
        </li>
      </ul>
      <p>当前标题：{{ value.listing.before.title }}</p>
      <pre>{{ value.listing.before.description || '当前描述为空' }}</pre>
      <p>拟保存标题：{{ value.listing.product.name }}</p>
      <pre>{{ value.listing.product.facts }}</pre>
    </details>
  </section>
</template>

<style scoped>
.margin-evidence {
  display: block;
  overflow-wrap: anywhere;
}
.margin-evidence article {
  border-top: 1px solid var(--line);
  margin-top: 1rem;
}
.margin-evidence pre {
  white-space: pre-wrap;
  font: inherit;
}
.margin-evidence summary {
  cursor: pointer;
}
</style>
