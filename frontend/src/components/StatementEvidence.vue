<script setup lang="ts">
import { entryTypes, type StatementItem } from '@/types/statements'
import { supportTime } from '@/types/support'
import SupportSource from './SupportSource.vue'
defineProps<{ line: StatementItem; shopId: number; timezone: string }>()
</script>
<template>
  <div class="statement-evidence">
    <p>
      <strong>{{ entryTypes[line.entry_type] }} · {{ line.currency }} {{ line.amount }}</strong>
    </p>
    <p>
      账单 {{ line.statement_id }} / 行 {{ line.line_id }} ·
      {{ supportTime(line.occurred_at, timezone) }}
    </p>
    <p v-if="line.evidence_ref">凭据费用行编号：{{ line.evidence_ref }}</p>
    <p v-if="line.fee_name">原始收费项：{{ line.fee_name }} · 成本类别待人工核对</p>
    <p>结算批号：{{ line.settlement_id || '未知' }} · 来源订单号：{{ line.order_id || '未知' }}</p>
    <p v-if="line.note" class="preserve-text">{{ line.note }}</p>
    <SupportSource :shop-id="shopId" :source="line.source" />
    <RouterLink :to="`/imports?shop=${shopId}&batch=${line.source.batch_id}`"
      >查看账单批次 #{{ line.source.batch_id }}</RouterLink
    >
  </div>
</template>
