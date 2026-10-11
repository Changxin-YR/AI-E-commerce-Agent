<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type {
  AgentRun,
  MarginEvidence,
  ListingCandidate,
  SupportCandidate,
  AnalysisExplanation,
  OperationExplanation,
} from '../services/agent-types'
import { sourcesIn } from '../services/agent-types'
import type { AnalysisResult } from '../services/analytics-types'
import type { ProductFacts } from '../services/listing-types'
import type { MessageFacts } from '../services/support-types'
import type { OperationTask } from '../services/operation-types'
import SourceList from './SourceList.vue'
const props = defineProps<{ run: AgentRun }>()
const output = (skill: string) =>
  props.run.steps.find((s) => s.skill === skill && s.status === 'completed')
    ?.output
const margin = computed(
  () => output('margin_evidence') as unknown as MarginEvidence | undefined,
)
const analysis = computed(
  () => output('metrics') as unknown as AnalysisResult | undefined,
)
const listing = computed(
  () => output('compose_listing') as unknown as ListingCandidate | undefined,
)
const support = computed(
  () => output('compose_support') as unknown as SupportCandidate | undefined,
)
const explanation = computed(
  () =>
    output('explain_analysis')?.explanation as AnalysisExplanation | undefined,
)
const operations = computed(
  () =>
    output('explain_operations')?.explanation as
      | OperationExplanation
      | undefined,
)
const productContext = computed(
  () =>
    output('product_context') as
      | {
          product?: ProductFacts
          active_id?: number
          before?: { title: string; description: string }
        }
      | undefined,
)
const messageContext = computed(
  () => output('message_context') as { message?: MessageFacts } | undefined,
)
const findings = computed(
  () =>
    (output('data_check')?.findings || []) as NonNullable<
      OperationTask['snapshot']
    >[],
)
const sources = computed(() => sourcesIn(props.run.steps.map((s) => s.output)))
const page = ref(1)
watch(
  () => props.run.id,
  () => {
    page.value = 1
  },
)
</script>
<template>
  <view>
    <view
      v-if="productContext?.product && !listing && !margin?.listing"
      class="card"
      ><text class="section-title">商品事实与草稿依据</text
      ><text
        >{{ productContext.product.sku }} ·
        {{ productContext.product.name }}</text
      ><text class="prose">{{ productContext.product.facts }}</text
      ><text class="label"
        >当前本地版本 #{{ productContext.active_id ?? '无' }}</text
      ><text>{{ productContext.before?.title }}</text
      ><text class="prose">{{ productContext.before?.description }}</text
      ><text class="hint">按名称和完整参数生成本地模板草稿。</text></view
    >
    <view v-if="messageContext?.message && !support" class="card"
      ><text class="section-title">人工客服草稿依据</text
      ><text class="prose">{{ messageContext.message.body }}</text
      ><text class="hint"
        >{{ messageContext.message.language }} · 订单
        {{
          messageContext.message.order_id
        }}；订单尚未核验，政策尚未选择，需人工接管。</text
      ></view
    >
    <view v-if="margin" class="card">
      <text class="section-title">最近7天复核依据</text>
      <text class="hint"
        >{{ margin.scope.start_at }} 至 {{ margin.scope.end_at }}（结束不含） ·
        {{ margin.scope.timezone }}</text
      >
      <text>{{ margin.cost_basis }}</text>
      <text class="hint"
        >纳入 {{ margin.included_lines }} 行；{{
          margin.ranking_available
            ? `低毛利命中 ${margin.candidate_count} 个 SKU`
            : '数据不足，完整毛利排行不可用'
        }}</text
      >
      <text>{{ margin.candidates.join('、') }}</text>
      <text v-for="gap in margin.data_gaps" :key="gap" class="error">{{
        gap
      }}</text>
      <text class="hint"
        >费用待核：{{ margin.fee_gaps.join('、') }}；尚无法核实净利润。</text
      >
      <view v-for="item in margin.recommendations" :key="item.kind" class="card"
        ><text class="label">{{ item.title }} · {{ item.risk }}</text
        ><text>{{ item.evidence }}</text
        ><text class="hint">{{ item.action }}</text></view
      >
      <text>{{ margin.listing_note }}</text>
      <view v-if="margin.listing"
        ><text class="label"
          >本地版本 #{{ margin.listing.active_id }} ·
          {{ margin.listing.product.sku }}</text
        ><text
          >遗漏参数：{{ margin.listing.missing_parameters.join('；') }}</text
        ><text class="label">当前标题 / 描述</text
        ><text>{{ margin.listing.before.title }}</text
        ><text class="prose">{{ margin.listing.before.description }}</text
        ><text class="label">拟保存标题 / 完整参数</text
        ><text>{{ margin.listing.product.name }}</text
        ><text class="prose">{{ margin.listing.product.facts }}</text></view
      >
    </view>
    <view v-if="analysis" class="card">
      <text class="section-title">销售与已知毛利依据</text
      ><text>{{ analysis.answer }}</text
      ><text class="hint"
        >{{ analysis.formula }} · {{ analysis.cost_basis }}</text
      >
      <text
        >销售 {{ analysis.summary.sales ?? '未知' }} · 成本
        {{ analysis.summary.cost ?? '未知' }} · 已知毛利
        {{ analysis.summary.gross_profit ?? '未知' }}
        {{ analysis.scope.currency }}</text
      >
      <text class="hint"
        >已知小计：销售 {{ analysis.summary.known_sales_subtotal }}（{{
          analysis.summary.sales_known_lines
        }}
        行），成本 {{ analysis.summary.known_cost_subtotal }}（{{
          analysis.summary.cost_known_lines
        }}
        行）</text
      >
      <text v-for="warning in analysis.warnings" :key="warning" class="error">{{
        warning
      }}</text
      ><text class="hint">费用缺口：{{ analysis.fee_gaps.join('；') }}</text>
      <view v-for="sku in analysis.skus" :key="String(sku.sku)" class="card"
        ><text>{{ sku.sku }} · {{ sku.purchased_quantity }} 件</text
        ><text class="hint"
          >销售 {{ sku.sales ?? '未知' }} · 已知毛利
          {{ sku.gross_profit ?? '未知' }} · 毛利率
          {{ sku.margin_percent ?? '未知' }}%</text
        ></view
      >
      <view
        v-for="line in analysis.lines.slice(0, page * 20)"
        :key="line.source.row_id"
        class="card"
        ><text
          >{{ line.order_id }} / {{ line.line_id }} · {{ line.sku }} ·
          {{ line.included ? '计入' : '排除' }}</text
        ><text class="hint"
          >{{ line.quantity }} 件 × {{ line.unit_price }} {{ line.currency }} ·
          折扣 {{ line.discount ?? '未知' }} · 退款
          {{ line.refund ?? '未知' }}</text
        ><text class="hint"
          >销售 {{ line.sales ?? '未知' }} · 成本 {{ line.cost ?? '未知' }} ·
          已知毛利 {{ line.gross_profit ?? '未知' }}</text
        ><text class="error">{{ line.gaps.join('；') }}</text></view
      >
      <button v-if="analysis.lines.length > page * 20" @tap="page++">
        继续查看订单行
      </button>
    </view>
    <view v-if="explanation" class="card"
      ><text class="section-title">事实解释</text
      ><text v-for="item in explanation.observations" :key="item.fact_id"
        >{{ item.sku }} · {{ item.text }}</text
      ><text v-for="item in explanation.checks" :key="item.id" class="hint">{{
        item.text
      }}</text></view
    >
    <view v-if="operations" class="card"
      ><text class="section-title">运营检查概览</text
      ><text v-for="branch in operations.branches" :key="branch.id"
        >{{ branch.name }} · {{ branch.status }} · {{ branch.count }} ·
        {{ branch.reason }}</text
      ><text v-for="item in operations.checks" :key="item.id" class="hint">{{
        item.text
      }}</text></view
    >
    <view v-for="(finding, index) in findings" :key="index" class="card"
      ><text class="label"
        >{{ finding.title }} · {{ finding.object_label }}</text
      ><text>{{ finding.basis }}</text
      ><text>{{ finding.advice }}</text
      ><text class="hint">{{ finding.impact }}</text
      ><text v-for="(value, key) in finding.facts" :key="key" class="hint"
        >{{ key }}：{{ value }}</text
      ></view
    >
    <view v-if="listing" class="card"
      ><text class="section-title">Listing 候选审阅</text
      ><text
        >{{ listing.preparation.product.sku }} ·
        {{ listing.preparation.product.name }}</text
      ><text class="prose">{{ listing.preparation.product.facts }}</text
      ><text class="label">当前版本</text
      ><text>{{ listing.preparation.before?.title || '无' }}</text
      ><text class="prose">{{ listing.preparation.before?.description }}</text
      ><text class="label">拟保存候选</text
      ><text>{{ listing.candidate.title }}</text
      ><text class="prose">{{ listing.candidate.description }}</text
      ><text class="hint"
        >{{ listing.engine }} · 保存后仍需在 Listing 页面审批生效。</text
      ></view
    >
    <view v-if="support" class="card"
      ><text class="section-title">客服候选全文</text
      ><text class="prose">{{ support.candidate.message.body }}</text
      ><text class="hint"
        >订单{{ support.candidate.order_verified ? '已核对' : '未核验' }} ·
        {{ support.candidate.intents.join('、') }}</text
      ><text class="error">{{ support.candidate.reasons.join('；') }}</text
      ><text>{{ support.candidate.handoff_summary }}</text
      ><text class="prose">{{ support.candidate.reply }}</text
      ><view v-for="policy in support.candidate.policies" :key="policy.id"
        ><text class="label"
          >政策 #{{ policy.id }} {{ policy.data?.title }}</text
        ><text class="prose">{{ policy.data?.text }}</text></view
      ></view
    >
    <SourceList :sources="sources" :shop-id="run.shop_id" />
  </view>
</template>
<style scoped>
.prose {
  display: block;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
