<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import {
  orderComparisonReasons,
  orderComparisonStatuses,
  type OrderReconciliation,
} from '@/types/orderReconciliation'
import { supportTime } from '@/types/support'
import StatementEvidence from './StatementEvidence.vue'
import SupportSource from './SupportSource.vue'

const props = defineProps<{ result: OrderReconciliation; shopId: number }>()
const filterId = useId()
const filter = ref('all')
const limit = ref(20)
const orders = computed(() => new Map(props.result.orders.map((line) => [line.id, line])))
const statements = computed(() => new Map(props.result.statements.map((line) => [line.id, line])))
const filtered = computed(() =>
  props.result.comparisons.filter((item) => filter.value === 'all' || item.status === filter.value),
)
</script>
<template>
  <section class="form-panel section-block reconciliation-result" aria-label="订单金额待核清单">
    <h2>订单与账单，按依据核对</h2>
    <p>
      读取于 {{ supportTime(result.calculated_at, result.scope.timezone) }} · 来源版本
      {{ result.source_revision }}
    </p>
    <p>
      {{ supportTime(result.scope.start_at, result.scope.timezone) }} 至
      {{ supportTime(result.scope.end_at, result.scope.timezone) }}（不含结束）
    </p>
    <p>
      窗内订单 {{ result.orders.filter((o) => o.in_window).length }} 行 · 窗内销售/退款账单
      {{ result.statements.filter((s) => s.in_window).length }} 行 · 窗口外关联来源
      {{
        result.orders.filter((o) => !o.in_window).length +
        result.statements.filter((s) => !s.in_window).length
      }}
      行
    </p>
    <p>文件覆盖完整性未知。每项差额仅代表当前导入记录在所选口径下的比较。</p>
    <p v-if="result.scope.sale_basis === 'unknown'">销售金额口径：未知</p>
    <div v-else class="data-note">
      <div>
        <h3>本次采用的卖家声明</h3>
        <p>两侧均为退款前的折后商品款，不含运费、税费及其他调整。</p>
        <p class="preserve-text">依据：{{ result.scope.basis_note }}</p>
      </div>
    </div>
    <details class="section-block">
      <summary>完整核对口径与待补依据</summary>
      <ul>
        <li v-for="check in result.checks" :key="check">{{ check }}</li>
      </ul>
    </details>
    <div class="form-field section-block">
      <label :for="filterId">订单核对状态</label>
      <select :id="filterId" v-model="filter" @change="limit = 20">
        <option value="all">全部（{{ result.comparisons.length }}）</option>
        <option v-for="(label, key) in orderComparisonStatuses" :key="key" :value="key">
          {{ label }}（{{ result.comparisons.filter((c) => c.status === key).length }}）
        </option>
      </select>
    </div>
    <p v-if="!result.comparisons.length">此范围没有候选来源；无法判断实际销售或退款是否发生。</p>
    <p v-else-if="!filtered.length">当前筛选无核对条目。</p>
    <article
      v-for="(item, index) in filtered.slice(0, limit)"
      :key="`${item.order_id}-${item.entry_type}-${index}`"
      class="comparison section-block"
    >
      <h3>
        {{ item.order_id || '未提供订单号' }} · {{ item.entry_type === 'sale' ? '销售款' : '退款' }}
      </h3>
      <p>
        <strong>{{ orderComparisonStatuses[item.status] }}</strong>
      </p>
      <p v-if="item.difference !== null">
        差额 {{ item.currency }} {{ item.difference }} · 账单销售款 − 订单折后商品款
        {{ item.order_amount }}
      </p>
      <ul v-if="item.reasons.length">
        <li v-for="reason in item.reasons" :key="reason">
          {{ orderComparisonReasons[reason] ?? reason }}
        </li>
      </ul>
      <details>
        <summary>
          查看关联来源（订单 {{ item.order_line_ids.length }} 行 / 账单
          {{ item.statement_ids.length }} 行）
        </summary>
        <template v-for="id in item.order_line_ids" :key="`o-${id}`">
          <div v-if="orders.get(id)" class="source-block section-block">
            <h4>
              订单 {{ orders.get(id)!.order_id }} / 行 {{ orders.get(id)!.line_id }} ·
              {{ orders.get(id)!.in_window ? '窗内来源' : '窗口外关联' }}
            </h4>
            <p>
              SKU {{ orders.get(id)!.sku }} · 状态 {{ orders.get(id)!.status }} ·
              {{ supportTime(orders.get(id)!.ordered_at, result.scope.timezone) }}
            </p>
            <p>
              数量 {{ orders.get(id)!.quantity }} × 单价 {{ orders.get(id)!.currency }}
              {{ orders.get(id)!.unit_price }} · 行折扣 {{ orders.get(id)!.discount ?? '未知' }} ·
              累计行退款 {{ orders.get(id)!.refund ?? '未知' }}
            </p>
            <SupportSource :shop-id="shopId" :source="orders.get(id)!.source" />
            <RouterLink :to="`/imports?shop=${shopId}&batch=${orders.get(id)!.source.batch_id}`"
              >查看订单批次 #{{ orders.get(id)!.source.batch_id }}</RouterLink
            >
          </div>
        </template>
        <template v-for="id in item.statement_ids" :key="`s-${id}`">
          <div v-if="statements.get(id)" class="source-block section-block">
            <p>{{ statements.get(id)!.in_window ? '窗内来源' : '窗口外关联' }}</p>
            <StatementEvidence
              :line="statements.get(id)!"
              :shop-id="shopId"
              :timezone="result.scope.timezone"
            />
          </div>
        </template>
      </details>
    </article>
    <button v-if="limit < filtered.length" class="button secondary" @click="limit += 20">
      显示更多核对条目
    </button>
  </section>
</template>
<style scoped>
.reconciliation-result {
  overflow-wrap: anywhere;
}
.comparison {
  border-top: 1px solid var(--line);
  padding-top: 20px;
}
.source-block {
  padding-left: 16px;
  border-left: 2px solid var(--line);
}
</style>
