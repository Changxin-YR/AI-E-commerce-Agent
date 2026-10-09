<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { scopeQuery } from '@/composables/deepLink'
import type {
  AgentAction,
  AgentBudget,
  AgentRun,
  AnalysisExplanation,
  ListingCandidate,
  SupportCandidate,
  OperationExplanation,
} from '@/types/agent'
import { agentLabels, agentReasons, sourcesIn } from '@/types/agent'
import { sourceLabels } from '@/types/operations'
import type { OperationTask } from '@/types/operations'
import type { AnalysisResult } from '@/types/analytics'
import AnalysisEvidence from './AnalysisEvidence.vue'
import AnalysisNarrative from './AnalysisNarrative.vue'
import ListingCandidatePreview from './ListingCandidatePreview.vue'
import SupportCandidatePreview from './SupportCandidatePreview.vue'
import OperationNarrative from './OperationNarrative.vue'
import OperationFindingPreview from './OperationFindingPreview.vue'
import SourceEvidence from './SupportSource.vue'
import { supportTime } from '@/types/support'
const props = defineProps<{
  run: AgentRun
  busy: boolean
  returnContext?: Record<string, string>
}>()
const emit = defineEmits<{ action: [action: AgentAction, budget?: AgentBudget] }>()
const budget = reactive<AgentBudget>({ max_steps: 12, max_seconds: 120, max_cost_usd: '0' })
watch(
  () => props.run.id,
  () => Object.assign(budget, props.run.budget),
  { immediate: true },
)
const sources = computed(() => sourcesIn(props.run.steps.map((s) => s.output)))
const check = computed(
  () => props.run.steps.find((s) => s.skill === 'data_check' && s.status === 'completed')?.output,
)
const findings = computed(
  () => (check.value?.findings ?? []) as NonNullable<OperationTask['snapshot']>[],
)
const branches = computed(
  () => (check.value?.branches ?? []) as { name: string; status: string; reason: string }[],
)
const analysis = computed(
  () =>
    props.run.steps.find((s) => s.skill === 'metrics' && s.status === 'completed')
      ?.output as unknown as AnalysisResult | undefined,
)
const explanation = computed(
  () =>
    props.run.steps.find((step) => step.node === 'explain_analysis' && step.status === 'completed')
      ?.output?.explanation as AnalysisExplanation | undefined,
)
const resumable = computed(() => ['paused', 'waiting_configuration'].includes(props.run.status))
const operationExplanation = computed(
  () =>
    props.run.steps.find((s) => s.node === 'explain_operations' && s.status === 'completed')?.output
      ?.explanation as OperationExplanation | undefined,
)
const supportCandidate = computed(
  () =>
    props.run.steps.find(
      (s) => s.node === 'compose_support' && s.status === 'completed' && s.output?.candidate,
    )?.output as unknown as SupportCandidate | undefined,
)
const listingCandidate = computed(
  () =>
    props.run.steps.find(
      (s) => s.node === 'compose_listing' && s.status === 'completed' && s.output?.candidate,
    )?.output as unknown as ListingCandidate | undefined,
)
const stoppable = computed(() =>
  [
    'ready',
    'running',
    'paused',
    'waiting_configuration',
    'waiting_approval',
    'waiting_input',
  ].includes(props.run.status),
)
const recordLink = computed(() => {
  const kind = String(props.run.result?.record_type)
  const entry = (
    {
      operations: ['/', 'run'],
      listing: ['/listings', 'listing'],
      support: ['/support', 'draft'],
      analysis: ['/analytics', 'analysis'],
    } as Record<string, string[]>
  )[kind]
  if (!entry) return undefined
  return {
    path: entry[0]!,
    query: {
      shop: props.run.shop_id,
      ...props.returnContext,
      ...scopeQuery(props.run.input?.scope ?? {}),
      [entry[1]!]: String(props.run.result?.record_id),
    },
  }
})
const actionLabels: Record<string, string> = {
  business_rules_changed: '经营规则已变化',
  started: '已启动',
  approve: '卖家已批准',
  reject: '卖家已拒绝',
  pause: '卖家已暂停',
  resume: '卖家已恢复',
  cancel: '卖家已取消',
}
</script>

<template>
  <section class="agent-review section-block" aria-label="任务执行详情">
    <div class="section-title">
      <h2>任务 #{{ run.id }}</h2>
      <span class="outline-label">{{ agentLabels[run.status] ?? run.status }}</span>
    </div>
    <p>
      {{ sourceLabels[run.source_status] }} ·
      {{ agentLabels[run.model_status] ?? run.model_status }} · 外部未提交
    </p>
    <p>当前步骤：{{ agentLabels[run.next_node] ?? run.next_node }}</p>
    <p v-if="run.authorization_id">
      绑定 R1 预授权 #{{ run.authorization_id }} · 消耗与撤回见下方授权记录
    </p>
    <p>
      启动于 {{ supportTime(run.created_at, run.input?.scope.timezone ?? 'Asia/Shanghai') }} ·
      来源版本 {{ run.source_revision }}
    </p>
    <p v-if="agentReasons[run.reason]" role="status">{{ agentReasons[run.reason] }}</p>
    <p v-if="run.source_status === 'stale'">
      来源、经营规则已变化或过期。保留历史结果，需使用当前数据和规则新建任务。
    </p>
    <RouterLink
      v-if="run.input?.scope.rule_revision_id"
      :to="{
        path: '/rules',
        query: {
          shop: run.shop_id,
          channel: run.input.scope.channel,
          identity: run.input.scope.data_identity,
          version: run.input.scope.rule_revision_id,
        },
      }"
      >查看使用的经营规则 #{{ run.input.scope.rule_revision_id }}</RouterLink
    >
    <div class="analysis-metrics">
      <div>
        <small>执行步数</small><strong>{{ run.steps_used }} / {{ run.budget.max_steps }}</strong>
      </div>
      <div>
        <small>累计执行时间</small><strong>{{ (run.elapsed_ms / 1000).toFixed(2) }} 秒</strong
        ><small>上限 {{ run.budget.max_seconds }} 秒</small>
      </div>
      <div>
        <small>模型费用（USD，按配置费率）</small><strong>{{ run.spent_usd }}</strong
        ><small>预算 {{ run.budget.max_cost_usd }}</small>
      </div>
      <div>
        <small>在途 / 未确认费用预留（USD）</small><strong>{{ run.reserved_usd }}</strong
        ><small>取消后在途请求仍可能产生费用</small>
      </div>
    </div>
    <div v-if="branches.length && !operationExplanation" class="agent-branches">
      <p v-for="branch in branches" :key="branch.name">
        <strong>{{ branch.name }}：</strong>{{ branch.reason }}
      </p>
    </div>
    <AnalysisNarrative
      v-if="analysis && run.template === 'question'"
      :analysis="analysis"
      :explanation="explanation"
    />
    <ListingCandidatePreview v-if="listingCandidate" :value="listingCandidate" />
    <SupportCandidatePreview v-if="supportCandidate" :value="supportCandidate" />
    <OperationNarrative v-if="operationExplanation" :value="operationExplanation" />
    <p v-if="operationExplanation && run.input">
      本次范围：{{ run.input.scope.channel }} · {{ run.input.scope.data_identity }} ·
      {{ run.input.scope.currency }} ·
      {{ supportTime(run.input.scope.start_at, run.input.scope.timezone) }} 至
      {{ supportTime(run.input.scope.end_at, run.input.scope.timezone) }}（结束不含，{{
        run.input.scope.timezone
      }}）。 商品按店铺读取，订单按此窗口和渠道检查；消息和库存取当前导入记录。
    </p>
    <div v-if="run.status === 'waiting_approval'" class="data-note">
      <h3>审批当前内部写入 · R1 · 费用 0 USD</h3>
      <p>
        影响店铺 #{{ run.shop_id }}。{{
          run.next_node === 'propose_tasks'
            ? '将下列异常保存为待审批候选，再到工作台逐项处理。'
            : run.next_node === 'analysis_todo'
              ? '保存上方统计快照，并创建一个「核对销售与已知毛利及缺失费用」待办；相同来源和口径复用记录。'
              : run.next_node === 'listing_candidate'
                ? '保存上方已核对的模型候选为待审 Listing，随后在业务页面单独审批生效；相同来源、基线及文案复用记录。'
                : run.next_node === 'listing_draft'
                  ? '按商品名称和完整参数生成本地模板草稿，在 Listing 页面查看差异并单独审批生效。'
                  : run.next_node === 'support_candidate'
                    ? '将上方候选保存为本地客服草稿；需人工接管的原因随草稿保留，客服页面可编辑和存档。'
                    : '保存未核验订单、未选择政策的人工接管草稿，在客服页面继续核对。'
        }}
      </p>
      <p v-if="run.next_node === 'analysis_todo'">
        待办可完成或重开，历史统计保留；来源清除将擦除相关快照。
      </p>
      <p v-else>候选可忽略，草稿可拒绝或存档；已有生效版本由业务页面管理。</p>
      <OperationFindingPreview
        v-for="(finding, index) in findings"
        :key="index"
        :finding="finding"
        :shop="run.shop_id"
      />
      <div class="button-row">
        <button
          class="button primary"
          :disabled="busy || run.source_status !== 'current'"
          @click="emit('action', 'approve')"
        >
          批准当前节点
        </button>
        <button class="button secondary" :disabled="busy" @click="emit('action', 'reject')">
          拒绝当前节点
        </button>
      </div>
    </div>
    <details v-if="run.status !== 'waiting_approval' && findings.length" class="section-block">
      <summary>查看检查时的 {{ findings.length }} 项候选</summary>
      <OperationFindingPreview
        v-for="(finding, index) in findings"
        :key="index"
        :finding="finding"
        :shop="run.shop_id"
      />
    </details>
    <div class="button-row">
      <button
        v-if="run.status === 'ready'"
        class="button primary"
        :disabled="busy"
        @click="emit('action', 'advance')"
      >
        继续执行
      </button>
      <button
        v-if="['ready', 'running'].includes(run.status)"
        class="button secondary"
        @click="emit('action', 'pause')"
      >
        暂停任务
      </button>
      <button v-if="stoppable" class="button secondary" @click="emit('action', 'cancel')">
        取消任务
      </button>
      <RouterLink v-if="recordLink" :to="recordLink" class="button secondary"
        >到业务页面复查 #{{ run.result?.record_id }}</RouterLink
      >
    </div>
    <form v-if="resumable" @submit.prevent="emit('action', 'resume', { ...budget })">
      <p
        v-if="['question', 'listing_model', 'support_model', 'daily_model'].includes(run.template)"
      >
        暂停期间丢弃的模型结果，在恢复时会重新请求并计费；已用费用计入总预算。
        在途或未确认费用尚未解除时，服务器会阻止恢复。
      </p>
      <fieldset class="analysis-fields" :disabled="busy">
        <label
          >恢复后总步数上限<input
            v-model.number="budget.max_steps"
            type="number"
            :min="run.budget.max_steps"
            max="100"
            required
        /></label>
        <label
          >恢复后总秒数上限<input
            v-model.number="budget.max_seconds"
            type="number"
            :min="run.budget.max_seconds"
            max="3600"
            required
        /></label>
        <label
          >恢复后总模型预算（USD）<input
            v-model="budget.max_cost_usd"
            type="number"
            :min="run.budget.max_cost_usd"
            max="10"
            step="0.000001"
            required
        /></label>
      </fieldset>
      <button class="button primary" :disabled="busy || run.source_status !== 'current'">
        确认预算并恢复
      </button>
    </form>
    <AnalysisEvidence v-if="analysis" :shop-id="run.shop_id" :result="analysis" />
    <details v-if="sources.length" class="section-block">
      <summary>查看 {{ sources.length }} 条事实来源</summary>
      <SourceEvidence
        v-for="source in sources"
        :key="source.row_id"
        :shop-id="run.shop_id"
        :source="source"
      />
    </details>
    <h3>步骤与操作记录</h3>
    <ol class="agent-steps">
      <li v-for="step in run.steps" :key="step.id">
        <strong
          >{{ agentLabels[step.node] ?? step.node }} ·
          {{ agentLabels[step.status] ?? step.status }}</strong
        >
        <p v-if="step.skill">
          技能 {{ step.skill }} v{{ step.skill_version }} · {{ step.duration_ms }} ms
        </p>
        <p v-if="step.reason">
          {{ agentReasons[step.reason] ?? actionLabels[step.reason] ?? step.reason }}
        </p>
        <p v-if="step.next_node">下一步：{{ agentLabels[step.next_node] ?? step.next_node }}</p>
        <details v-if="step.input || step.output">
          <summary>查看节点输入与结果</summary>
          <pre>{{ JSON.stringify({ input: step.input, output: step.output }, null, 2) }}</pre>
        </details>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.agent-review {
  min-width: 0;
  overflow-wrap: anywhere;
}
.agent-review pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 12px;
  max-height: 420px;
  overflow-y: auto;
}
.agent-steps {
  padding-left: 22px;
}
.agent-steps li {
  border-bottom: 1px solid var(--line);
  padding: 18px 0;
}
.agent-branches {
  border-left: 3px solid var(--green);
  padding-left: 18px;
}
</style>
