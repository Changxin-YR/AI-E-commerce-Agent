<script setup lang="ts">
import type { SupportCandidate } from '@/types/agent'
import { agentLabels } from '@/types/agent'
import { intentLabels } from '@/types/support'
defineProps<{ value: SupportCandidate }>()
function intentText(intents: string[]): string {
  return intents.map((intent) => intentLabels[intent] ?? intent).join('、')
}
</script>
<template>
  <section class="section-block support-candidate" aria-label="模型客服候选预览">
    <h3>回复候选 · {{ value.candidate.reasons.length ? '需要人工接管' : '等待人工审阅' }}</h3>
    <p>
      {{ agentLabels[value.engine] ?? value.engine }} · 消息 #{{
        value.candidate.message.message_id
      }}
      · 外部未提交
    </p>
    <div class="candidate-columns">
      <div>
        <h4>客户原文</h4>
        <p class="preserve-text">{{ value.candidate.message.body }}</p>
        <p>诉求：{{ intentText(value.candidate.intents) }}</p>
        <p>订单关联：{{ value.candidate.order_verified ? '卖家人工已核验' : '尚未核验' }}</p>
      </div>
      <div>
        <h4>拟保存回复</h4>
        <p class="preserve-text">
          {{ value.candidate.reply || '语言待核实，请人工翻译后补充回复。' }}
        </p>
      </div>
    </div>
    <h4>人工接管摘要与证据</h4>
    <p>{{ value.candidate.handoff_summary }}</p>
    <ul>
      <li v-for="reason in value.candidate.reasons" :key="reason">{{ reason }}</li>
    </ul>
    <ul>
      <li v-for="fact in value.candidate.model_facts" :key="fact">{{ fact }}</li>
    </ul>
    <article
      v-for="policy in value.candidate.policies"
      :key="policy.id"
      class="support-policy-quote"
    >
      <h4>{{ policy.data?.title }} · v{{ policy.number }}</h4>
      <p>出处：{{ policy.data?.source }} · 来源版本 {{ policy.data?.source_version }}</p>
      <p class="preserve-text">{{ policy.data?.text }}</p>
    </article>
    <p>
      批准后新增本地草稿，相同候选复用既有记录；已有草稿正文和处理状态保留。保存后可在客服页面修改、标记人工处理或存档。
    </p>
  </section>
</template>
<style scoped>
.support-candidate {
  overflow-wrap: anywhere;
}
.candidate-columns {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 24px;
}
@media (max-width: 680px) {
  .candidate-columns {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
