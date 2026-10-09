<script setup lang="ts">
import { computed, ref } from 'vue'
import type { SettlementSnapshot } from '@/types/settlements'
import { payoutStatuses } from '@/types/settlements'
import { entryTypes } from '@/types/statements'
import { supportTime } from '@/types/support'
import StatementEvidence from './StatementEvidence.vue'
const props = defineProps<{ result: SettlementSnapshot; shopId: number; historical?: boolean }>()
const limit = ref(20)
const byId = computed(() => new Map(props.result.statements.map((s) => [s.id, s])))
const totalLabels: Record<string, string> = {
  ...entryTypes,
  manual_receipt: '卖家登记到账 · 银行待核',
}
</script>
<template>
  <div class="settlement-result">
    <h3>{{ historical ? '存档时依据' : '本次读取依据' }} · {{ result.content.statement_id }}</h3>
    <p>
      卖家登记周期：{{ supportTime(result.scope.start_at, result.scope.timezone) }} 至
      {{ supportTime(result.scope.end_at, result.scope.timezone) }}（结束不含，{{
        result.scope.timezone
      }}）
    </p>
    <p>
      来源版本 {{ result.source_revision }} ·
      {{ supportTime(result.calculated_at, result.scope.timezone) }}
    </p>
    <p class="data-note">覆盖完整性未知 · 期初期末余额未知 · 银行证据未核验</p>
    <p class="preserve-text">{{ result.content.note }}</p>
    <ul>
      <li v-for="t in result.totals" :key="`${t.currency}-${t.entry_type}`">
        {{ totalLabels[t.entry_type] }}：{{ t.currency }} {{ t.amount }} · {{ t.count }} 笔
      </li>
    </ul>
    <p v-if="!result.statements.length">
      该原账单号没有当前有效明细，请检查渠道、数据身份或导入文件。
    </p>
    <p v-if="result.outside_cycle_ids.length">
      {{
        result.outside_cycle_ids.length
      }}
      行非回款明细在登记周期之外，需核实归属；保留在全部原账单明细中。
    </p>
    <h4>逐笔回款比较</h4>
    <p v-if="!result.comparisons.length">没有平台回款或人工到账登记可供比较。</p>
    <article
      v-for="(c, index) in result.comparisons.slice(0, limit)"
      :key="index"
      class="comparison"
    >
      <strong>{{ payoutStatuses[c.status] }} · {{ c.payout_ref || '凭据号未知' }}</strong>
      <p v-if="c.difference !== null">差额（平台减人工）：{{ c.difference }}</p>
      <details>
        <summary>展开双方凭据</summary>
        <template v-for="id in c.statement_ids" :key="id"
          ><StatementEvidence
            v-if="byId.get(id)"
            :line="byId.get(id)!"
            :shop-id="shopId"
            :timezone="result.scope.timezone"
        /></template>
        <div v-for="i in c.receipt_indexes" :key="i">
          <template v-if="result.content.receipts[i]">
            <p>
              <strong>卖家人工到账登记 · {{ result.content.receipts[i]!.receipt_ref }}</strong>
            </p>
            <p>
              {{ result.content.receipts[i]!.currency }} {{ result.content.receipts[i]!.amount }} ·
              {{
                supportTime(
                  result.content.receipts[i]!.received_at,
                  result.content.receipts[i]!.timezone,
                )
              }}（{{ result.content.receipts[i]!.timezone }}）
            </p>
            <p class="preserve-text">{{ result.content.receipts[i]!.note }}</p>
          </template>
        </div>
      </details>
    </article>
    <button v-if="limit < result.comparisons.length" class="button secondary" @click="limit += 20">
      更多回款比较
    </button>
    <details>
      <summary>全部原账单明细（{{ result.statements.length }}）</summary>
      <StatementEvidence
        v-for="s in result.statements.slice(0, limit)"
        :key="s.id"
        :line="s"
        :shop-id="shopId"
        :timezone="result.scope.timezone"
      />
      <button v-if="limit < result.statements.length" class="button secondary" @click="limit += 20">
        更多账单明细
      </button>
    </details>
    <details>
      <summary>核对口径与待补资料</summary>
      <ul>
        <li v-for="c in result.checks" :key="c">{{ c }}</li>
      </ul>
    </details>
  </div>
</template>
<style scoped>
.settlement-result {
  overflow-wrap: anywhere;
}
.comparison {
  border-top: 1px solid var(--line);
  padding-block: 18px;
}
.preserve-text {
  white-space: pre-wrap;
}
details {
  margin-block: 12px;
}
li {
  margin-block: 8px;
}
</style>
