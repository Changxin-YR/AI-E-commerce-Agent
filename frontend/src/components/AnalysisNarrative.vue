<script setup lang="ts">
import type { AnalysisResult } from '@/types/analytics'
import type { AnalysisExplanation } from '@/types/agent'
import { supportTime } from '@/types/support'
defineProps<{ analysis: AnalysisResult; explanation?: AnalysisExplanation }>()
</script>

<template>
  <section class="section-block evidence-story" aria-label="经营问数解释">
    <h3>经营事实与核对建议</h3>
    <p>
      {{ analysis.scope.data_identity === 'synthetic' ? '合成测试数据' : '用户导入数据' }} ·
      {{ analysis.scope.currency }} · 全店所选身份 · 数据版本 {{ analysis.source_revision }}
    </p>
    <p>
      {{ supportTime(analysis.scope.start_at, analysis.scope.timezone) }} 至
      {{ supportTime(analysis.scope.end_at, analysis.scope.timezone) }}（不含终点）
    </p>
    <p>
      计算完成：{{ supportTime(analysis.calculated_at, analysis.scope.timezone) }}。
      各来源导出截至时间见原始行证据；未知截至时间不能推断。
    </p>
    <template v-if="explanation">
      <p>{{ explanation.composition }}</p>
      <ol>
        <li v-for="item in explanation.observations" :key="item.fact_id">
          <p>{{ item.text }}</p>
          <small
            >可核对依据 ·
            {{
              item.sku ? '对应 SKU 的收入、成本与原始行见下方证据' : '当前口径的统计与缺口说明'
            }}</small
          >
        </li>
      </ol>
      <h4 v-if="explanation.checks.length">建议核对（原因尚待验证）</h4>
      <ul>
        <li v-for="item in explanation.checks" :key="item.id">{{ item.text }}</li>
      </ul>
      <p>
        模型最多看到 {{ explanation.sku_fact_limit }} 项匿名 SKU
        指标；完整筛选结果与明细以本地统计为准。
      </p>
    </template>
    <p v-else>本地统计已完成，模型解释尚未完成。</p>
    <p v-if="!explanation">{{ analysis.answer }}</p>
    <p v-if="analysis.candidates.length">符合当前问题：{{ analysis.candidates.join('、') }}</p>
    <p>{{ analysis.formula }}</p>
    <p>{{ analysis.cost_basis }}</p>
    <ul>
      <li v-for="item in analysis.warnings" :key="item">{{ item }}</li>
    </ul>
  </section>
</template>

<style scoped>
.evidence-story {
  background: var(--white, #fff);
  border: 1px solid var(--line);
  border-left: 3px solid var(--green);
  padding: clamp(18px, 3vw, 28px);
  line-height: 1.75;
}
.evidence-story h3 {
  font-size: 18px;
  margin: 0 0 16px;
}
.evidence-story h4 {
  margin: 24px 0 8px;
}
.evidence-story p {
  margin: 10px 0;
}
.evidence-story ol {
  padding-left: 22px;
}
.evidence-story ol li {
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
}
.evidence-story small {
  color: var(--muted);
}
</style>
