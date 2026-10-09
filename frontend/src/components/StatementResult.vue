<script setup lang="ts">
import { computed, ref } from 'vue'
import { comparisonStatuses, entryTypes, type StatementReconciliation } from '@/types/statements'
import { supportTime } from '@/types/support'
import { expenseCategories } from '@/types/expenses'
import StatementEvidence from './StatementEvidence.vue'
const props = defineProps<{ result: StatementReconciliation; shopId: number }>()
const filter = ref('all')
const comparisonLimit = ref(20)
const lineLimit = ref(20)
const filtered = computed(() =>
  props.result.comparisons.filter((c) => filter.value === 'all' || c.status === filter.value),
)
const byId = computed(() => new Map(props.result.statements.map((line) => [line.id, line])))
</script>
<template>
  <section class="form-panel section-block statement-result" aria-label="账单核对结果">
    <h2>当前范围的账单与费用</h2>
    <p>
      读取于 {{ supportTime(result.calculated_at, result.scope.timezone) }} · 来源版本
      {{ result.source_revision }}
    </p>
    <p>
      {{ supportTime(result.scope.start_at, result.scope.timezone) }} 至
      {{ supportTime(result.scope.end_at, result.scope.timezone) }}（不含结束）
    </p>
    <p>
      有效账单 {{ result.statements.length }} 行 · 排除待重核费用
      {{ result.stale_expenses }} 笔、已撤销费用 {{ result.withdrawn_expenses }} 笔
    </p>
    <h3>按币种与类型合计</h3>
    <p v-if="!result.totals.length">此范围没有可计入账单行；不表示实际收支为零。</p>
    <ul>
      <li v-for="item in result.totals" :key="`${item.currency}-${item.entry_type}`">
        {{ entryTypes[item.entry_type] }} · {{ item.currency }} {{ item.amount }} ·
        {{ item.count }} 行
      </li>
    </ul>
    <details class="section-block">
      <summary>核对口径与待补依据</summary>
      <ul>
        <li v-for="check in result.checks" :key="check">{{ check }}</li>
      </ul>
    </details>
    <h3 class="section-block">费用差异清单</h3>
    <p>金额差额 = 账单费用 − 人工费用。重复编号与跨币种不计算差额；范围外记录可能造成单边缺失。</p>
    <div class="form-field">
      <label for="statement-filter">核对状态</label>
      <select id="statement-filter" v-model="filter" @change="comparisonLimit = 20">
        <option value="all">全部（{{ result.comparisons.length }}）</option>
        <option v-for="(label, key) in comparisonStatuses" :key="key" :value="key">
          {{ label }}（{{ result.comparisons.filter((c) => c.status === key).length }}）
        </option>
      </select>
    </div>
    <p v-if="!filtered.length">当前筛选无费用核对条目。</p>
    <article
      v-for="item in filtered.slice(0, comparisonLimit)"
      :key="`${item.evidence_ref}-${item.status}`"
      class="statement-comparison section-block"
    >
      <h4>{{ item.evidence_ref }} · {{ comparisonStatuses[item.status] }}</h4>
      <p v-if="item.difference !== null">
        差额 {{ item.expenses[0]?.currency }} {{ item.difference }}
      </p>
      <details>
        <summary>查看两侧依据</summary>
        <p v-if="!item.statement_ids.length">当前范围无对应账单费用行。</p>
        <template v-for="id in item.statement_ids" :key="id">
          <StatementEvidence
            v-if="byId.get(id)"
            :line="byId.get(id)!"
            :shop-id="shopId"
            :timezone="result.scope.timezone"
          />
        </template>
        <p v-if="!item.expenses.length">当前范围无对应有效人工费用。</p>
        <div v-for="expense in item.expenses" :key="expense.id" class="section-block">
          <p>
            人工费用：{{ expense.label }} · {{ expenseCategories[expense.category] }} ·
            {{ expense.currency }} {{ expense.amount }} · 版本
            {{ expense.version }}
          </p>
          <p>
            {{ supportTime(expense.occurred_at, result.scope.timezone) }} ·
            {{ expense.allocation === 'shop' ? '店铺未分摊' : '订单行全额归属' }}
          </p>
          <RouterLink :to="`/expenses?shop=${shopId}&expense=${expense.id}`"
            >查看人工费用 #{{ expense.id }}</RouterLink
          >
        </div>
      </details>
    </article>
    <button
      v-if="comparisonLimit < filtered.length"
      class="button secondary"
      @click="comparisonLimit += 20"
    >
      显示更多核对条目
    </button>
    <details class="section-block">
      <summary>全部当前账单明细（{{ result.statements.length }}）</summary>
      <StatementEvidence
        v-for="line in result.statements.slice(0, lineLimit)"
        :key="line.id"
        :line="line"
        :shop-id="shopId"
        :timezone="result.scope.timezone"
      />
      <button
        v-if="lineLimit < result.statements.length"
        class="button secondary"
        @click="lineLimit += 20"
      >
        显示更多账单行
      </button>
    </details>
  </section>
</template>
<style scoped>
.statement-result {
  overflow-wrap: anywhere;
}
.statement-comparison {
  border-top: 1px solid var(--line);
  padding-top: 1rem;
}
.statement-result :deep(.statement-evidence) {
  margin: 1rem 0;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 8px;
}
</style>
