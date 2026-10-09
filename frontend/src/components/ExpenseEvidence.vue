<script setup lang="ts">
import { expenseCategories, type ExpenseSnapshot } from '@/types/expenses'
import { supportTime } from '@/types/support'
import SupportSource from './SupportSource.vue'
defineProps<{ snapshot: ExpenseSnapshot; shopId: number }>()
</script>
<template>
  <div class="expense-evidence">
    <h3>
      {{ snapshot.content.label }} · {{ snapshot.content.currency }} {{ snapshot.content.amount }}
    </h3>
    <p>
      {{ expenseCategories[snapshot.content.category] }} ·
      {{ supportTime(snapshot.content.occurred_at, snapshot.content.timezone) }}
    </p>
    <p>
      {{
        snapshot.content.allocation === 'shop'
          ? '店铺费用 · 未分摊'
          : `订单 ${snapshot.order_id} / 行 ${snapshot.line_id} · SKU ${snapshot.sku} · 全额归属`
      }}
    </p>
    <p v-if="snapshot.source">
      关联时订单状态：{{ snapshot.order_status }}。请结合订单事实核对费用；本记录不证明结算或回款。
    </p>
    <dl>
      <dt>凭据编号</dt>
      <dd>{{ snapshot.content.evidence_ref }}</dd>
      <dt>事实依据</dt>
      <dd class="preserve-text">{{ snapshot.content.evidence_note }}</dd>
      <dt>录入或修订理由</dt>
      <dd class="preserve-text">{{ snapshot.content.reason }}</dd>
    </dl>
    <SupportSource v-if="snapshot.source" :shop-id="shopId" :source="snapshot.source" />
  </div>
</template>
