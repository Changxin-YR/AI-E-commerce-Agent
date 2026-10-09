<script setup lang="ts">
import type { OperationExplanation } from '@/types/agent'
defineProps<{ value: OperationExplanation }>()
const statuses: Record<string, string> = {
  checked: '已检查',
  partial: '部分检查',
  not_checked: '未检查',
}
</script>

<template>
  <section class="section-block" aria-label="运营检查解释">
    <h3>本次运营概览</h3>
    <p>{{ value.composition }}</p>
    <p>仅依据已导入文件；平台当前状态和实时物流待核对，已知商品毛利不是净利润。</p>
    <div class="analysis-metrics">
      <div v-for="item in value.candidate_counts" :key="item.kind">
        <small>{{ item.label }}</small
        ><strong>{{ item.count }} 项</strong>
      </div>
    </div>
    <article v-for="branch in value.branches" :key="branch.id" class="analysis-line">
      <strong>{{ branch.name }} · {{ statuses[branch.status] }} · {{ branch.count }} 行</strong>
      <p>{{ branch.reason }}</p>
    </article>
    <h4>接下来核对</h4>
    <ul>
      <li v-for="check in value.checks" :key="check.id">{{ check.text }}</li>
    </ul>
    <p v-if="value.next_action === 'finish'">没有生成异常候选。仍需留意上方未检查和缺失数据。</p>
  </section>
</template>
