<script setup lang="ts">
import { computed } from 'vue'
import type {
  AgentRun,
  AnalysisExplanation,
  ListingCandidate,
  SupportCandidate,
  OperationExplanation,
} from '@/types/agent'
import { agentReasons } from '@/types/agent'
import type { AnalysisResult } from '@/types/analytics'
const props = defineProps<{
  run: AgentRun
  busy: boolean
  canSave?: boolean
  confirmSave?: boolean
}>()
const emit = defineEmits<{ save: []; approve: []; dismiss: [] }>()
const output = (node: string) =>
  props.run.steps.find((step) => step.node === node && step.status === 'completed')?.output
const answer = computed(() =>
  String(output('answer')?.chat_answer ?? props.run.result?.chat_answer ?? ''),
)
const analysis = computed(
  () =>
    props.run.steps.find((step) => step.skill === 'metrics' && step.status === 'completed')
      ?.output as unknown as AnalysisResult | undefined,
)
const explanation = computed(
  () => output('explain_analysis')?.explanation as AnalysisExplanation | undefined,
)
const listing = computed(() => output('compose_listing') as unknown as ListingCandidate | undefined)
const support = computed(() => output('compose_support') as unknown as SupportCandidate | undefined)
const operations = computed(
  () => output('explain_operations')?.explanation as OperationExplanation | undefined,
)
// Earlier conversations predate localized answers. Show their recorded conclusion once.
const legacyAnswer = computed(() => {
  if (listing.value)
    return `${listing.value.candidate.title}\n\n${listing.value.candidate.description}`
  if (support.value) return support.value.candidate.reply || support.value.candidate.handoff_summary
  if (explanation.value)
    return explanation.value.observations
      .filter((item) => item.fact_id !== 'coverage')
      .slice(0, 2)
      .map((item) => item.text)
      .join('\n')
  if (analysis.value) return analysis.value.answer
  if (operations.value)
    return (
      operations.value.checks
        .slice(0, 2)
        .map((item) => item.text)
        .join('\n') || '本次检查已完成。'
    )
  return ''
})
const text = computed(
  () => answer.value || (props.run.input?.response_mode !== 'chat' ? legacyAnswer.value : ''),
)
const saveDescription = computed(
  () =>
    ({
      question: '保存这次分析，并创建一条销售与毛利核对待办。',
      listing_model: '保存以下原始商品文案为待审草稿。',
      support_model: '保存以下原始客户回复为本地草稿。',
      daily_model: '保存本次检查及异常候选，加入工作台待办。',
    })[props.run.template] ?? '保存本次业务结果。',
)
const saveAvailable = computed(
  () =>
    props.canSave &&
    props.run.source_status === 'current' &&
    (props.run.status === 'waiting_approval' ||
      (props.run.status === 'succeeded' && props.run.reason === 'chat_answered')) &&
    (props.run.template !== 'daily_model' ||
      !!(props.run.result?.check as { findings?: unknown[] } | undefined)?.findings?.length),
)
</script>

<template>
  <section class="answer" aria-label="AI 回答" :aria-busy="busy">
    <div v-if="run.input && run.source_status !== 'cleared'" class="question">
      <span>你</span>
      <p>{{ run.input.goal }}</p>
    </div>
    <div class="assistant-message">
      <span class="speaker">SoloOps</span>
      <p v-if="run.source_status === 'cleared'">这条回答的资料已清除，请重新提问。</p>
      <template v-else>
        <p v-if="run.source_status !== 'current'" class="notice">
          这是历史结论，资料已变化，请重新查询确认。
        </p>
        <p v-if="text" class="answer-text">{{ text }}</p>
        <p v-else-if="busy" role="status">正在整理结论…</p>
        <p v-else role="status">
          {{ agentReasons[run.reason] || '这次未能完成回答，请调整问题或数据范围后再试。' }}
        </p>
        <p
          v-if="
            text &&
            !busy &&
            [
              'blocked',
              'result_unknown',
              'circuit_open',
              'paused',
              'waiting_configuration',
            ].includes(run.status)
          "
          class="notice"
        >
          {{ agentReasons[run.reason] || '处理未完成，请重新核对当前状态。' }}
        </p>
        <button
          v-if="saveAvailable && !confirmSave"
          class="button secondary small"
          :disabled="busy"
          @click="emit('save')"
        >
          保存到工作台
        </button>
        <div
          v-if="confirmSave && saveAvailable"
          class="write-confirmation"
          role="region"
          aria-label="确认修改业务数据"
        >
          <strong>确认保存</strong>
          <p>{{ saveDescription }}</p>
          <p class="notice">
            店铺 #{{ run.shop_id }} ·
            {{ run.input?.scope.data_identity === 'synthetic' ? '样例资料' : '经营资料' }} ·
            {{ run.input?.scope.channel }}
          </p>
          <p v-if="listing" class="answer-text">
            {{ listing.candidate.title }}\n{{ listing.candidate.description }}
          </p>
          <p v-if="support" class="answer-text">
            {{ support.candidate.reply || support.candidate.handoff_summary }}
          </p>
          <p v-if="listing || support" class="notice">
            保存内容以上方原始草稿为准，聊天中的翻译供审阅；对外发布或发送另行确认。
          </p>
          <div class="button-row">
            <button
              class="button primary"
              :disabled="busy || run.source_status !== 'current'"
              @click="emit('approve')"
            >
              确认保存</button
            ><button class="button secondary" :disabled="busy" @click="emit('dismiss')">
              暂不保存
            </button>
          </div>
        </div>
        <p v-if="run.status === 'succeeded' && run.result?.record_id" class="notice">
          已保存到工作台。
        </p>
      </template>
    </div>
  </section>
</template>

<style scoped>
.answer {
  overflow-wrap: anywhere;
  line-height: 1.8;
}
.question {
  margin: 0 0 24px 12%;
  padding: 14px 20px;
  background: var(--green-soft, #edf4ee);
  border-radius: 16px;
}
.question p {
  margin: 3px 0;
  white-space: pre-wrap;
}
.question span,
.speaker {
  font-size: 12px;
  color: var(--muted);
}
.assistant-message {
  padding: 0 4px 24px;
}
.answer-text {
  white-space: pre-wrap;
  margin: 10px 0 18px;
  font-size: 16px;
}
.notice {
  color: var(--muted);
  font-size: 13px;
}
.write-confirmation {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 18px;
  margin-top: 16px;
}
</style>
