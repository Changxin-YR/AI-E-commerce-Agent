<template>
  <PageShell
    title="AI 运营"
    subtitle="受控执行：每一步都留痕，外部状态保持未提交。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <text class="section-title">创建运营任务</text>
    <view class="field">
      <text class="field__label">执行流程</text>
      <picker mode="selector" :range="templateOptions" range-key="label" :value="templateIndex" @change="setTemplate($event)">
        <view class="field__picker">{{ templateOptions[templateIndex]?.label }}</view>
      </picker>
    </view>

    <text class="section-title">范围与经营规则</text>
    <view v-for="field in scopeFields" :key="field.key" class="field">
      <text class="field__label">{{ field.label }}</text>
      <picker
        mode="selector"
        :range="field.options"
        range-key="label"
        :value="field.index"
        @change="setScopeChoice(field.key, field.options[Number(pickerValue($event))]?.key ?? '')"
      >
        <view class="field__picker">{{ field.options[field.index]?.label }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">业务时区（IANA）</text>
      <input class="field__input" :value="zone" :disabled="locked" @input="zone = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">币种</text>
      <input class="field__input" :value="currency" :disabled="locked" @input="currency = inputValue($event)" />
    </view>
    <template v-if="template !== 'margin_review'">
      <view class="field">
        <text class="field__label">开始时间</text>
        <picker mode="date" :value="startDay" @change="startDay = pickerValue($event)">
          <view class="field__picker">{{ startDay }}</view>
        </picker>
        <picker mode="time" :value="startClock" @change="startClock = pickerValue($event)">
          <view class="field__picker">{{ startClock }}</view>
        </picker>
      </view>
    </template>
    <view class="field">
      <text class="field__label">结束时间（不含终点）</text>
      <picker mode="date" :value="endDay" @change="endDay = pickerValue($event)">
        <view class="field__picker">{{ endDay }}</view>
      </picker>
      <picker mode="time" :value="endClock" @change="endClock = pickerValue($event)">
        <view class="field__picker">{{ endClock }}</view>
      </picker>
    </view>
    <text v-if="template === 'margin_review'" class="hint">开始时间自动取结束时间前精确 7 天。</text>
    <view class="field">
      <text class="field__label">最低销量</text>
      <input class="field__input" type="number" :value="quantity" :disabled="locked" @input="quantity = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">低毛利率上限 %</text>
      <input class="field__input" type="number" :value="margin" :disabled="locked" @input="margin = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">库存有效小时数</text>
      <input class="field__input" type="number" :value="age" :disabled="locked" @input="age = inputValue($event)" />
    </view>
    <FactLine v-if="rule" label="采用规则" :value="`#${rule.version} · ${rule.active === true ? '已启用' : '默认值'}`" />
    <ActionButton label="读取当前经营规则" :disabled="locked" @tap="readRule" />

    <view v-if="template === 'margin_review'" class="field">
      <text class="field__label">复核成本口径</text>
      <picker mode="selector" :range="costModes" range-key="label" :value="costModeIndex" @change="setCostMode($event)">
        <view class="field__picker">{{ costModes[costModeIndex]?.label }}</view>
      </picker>
    </view>

    <template v-if="needsObject">
      <view class="field">
        <text class="field__label">商品或消息关键词</text>
        <input class="field__input" :value="search" :disabled="locked" @input="search = inputValue($event)" />
      </view>
      <ActionButton label="搜索商品与消息" :disabled="locked" @tap="readOptions" />
    </template>

    <template v-if="needsProduct">
      <view class="field">
        <text class="field__label">目标商品</text>
        <picker mode="selector" :range="productOptions" range-key="label" :value="productIndex" @change="setProduct($event)">
          <view class="field__picker">{{ productOptions[productIndex]?.label }}</view>
        </picker>
      </view>
      <ActionButton label="加载更多商品" :disabled="locked" @tap="readOptions(true, false)" />
      <template v-if="product">
        <FactLine label="SKU" :value="product.sku" />
        <FactLine label="商品名称" :value="product.name" />
        <FactLine label="完整参数" :value="product.facts" />
      </template>
    </template>

    <template v-if="needsMessage">
      <view class="field">
        <text class="field__label">目标消息</text>
        <picker mode="selector" :range="messageOptions" range-key="label" :value="messageIndex" @change="setMessage($event)">
          <view class="field__picker">{{ messageOptions[messageIndex]?.label }}</view>
        </picker>
      </view>
      <ActionButton label="加载更多消息" :disabled="locked" @tap="readOptions(false, true)" />
      <template v-if="supportContext">
        <FactLine label="消息全文" :value="supportContext.message.body" />
        <FactLine label="标注语言" :value="supportContext.message.language" />
        <template v-if="template === 'support_model'">
          <FactLine
            v-for="order in supportContext.orders"
            :key="order.source.row_id"
            label="订单行"
            :value="`${order.order_id} / ${order.line_id} · ${order.sku} · ${order.status} · ${order.fulfillment_status}`"
          />
          <view class="row" @tap="orderVerified = !orderVerified">
            <text class="chip" :class="{ 'chip--active': orderVerified }">
              {{ orderVerified ? '已核验' : '未核验' }} · 已人工核验客户与上述全部订单行的关联
            </text>
          </view>
          <text class="hint">选择适用政策，最多 10 份。订单号相同不能证明买家身份。</text>
          <view
            v-for="policy in supportContext.policies"
            :key="policy.id"
            class="card"
            @tap="togglePolicy(policy.id)"
          >
            <text class="chip" :class="{ 'chip--active': policyIds.includes(policy.id) }">
              {{ policyIds.includes(policy.id) ? '已选' : '未选' }} · {{ policy.data?.title ?? '政策' }}
            </text>
          </view>
        </template>
      </template>
    </template>

    <template v-if="useModel">
      <view class="field">
        <text class="field__label">运营目标（最多 500 字）</text>
        <textarea class="field__input" :value="goal" :disabled="locked" @input="consentChanged(inputValue($event))" />
      </view>
      <template v-if="template === 'daily_model'">
        <ActionButton label="预览将发送的运营聚合数据" :disabled="locked" @tap="previewOperations" />
        <template v-if="operationContext">
          <FactLine label="来源版本" :value="operationContext.preview.source_revision" />
          <FactLine
            v-for="branch in operationContext.preview.branches"
            :key="branch.name"
            :label="`${branch.name} · ${branch.status}`"
            :value="`${branch.count} 行 · ${branch.reason}`"
          />
          <FactLine
            v-for="kindName in ['order_review', 'low_inventory', 'message_review', 'low_margin']"
            :key="kindName"
            :label="kindName"
            :value="operationContext.preview.findings.filter((item) => item.kind === kindName).length"
          />
        </template>
      </template>
      <text class="hint">{{ dataNotice }}</text>
      <view class="row" @tap="toggleAllowModel">
        <text class="chip" :class="{ 'chip--active': allowModel }">
          {{ allowModel ? '已同意' : '未同意' }} · 同意将本次目标文本发送至 {{ model?.provider ?? '未知' }}，使用下方 USD 预算
        </text>
      </view>
      <view v-if="template !== 'natural'" class="row" @tap="toggleAllowData">
        <text class="chip" :class="{ 'chip--active': allowData }">
          {{ allowData ? '已核对' : '未核对' }} · 已核对上述业务数据，同意按所列范围发送
        </text>
      </view>
    </template>

    <view class="field">
      <text class="field__label">最多执行步数（1–100）</text>
      <input class="field__input" type="number" :value="steps" :disabled="locked" @input="consentChangedBudget(inputValue($event), 'steps')" />
    </view>
    <view class="field">
      <text class="field__label">最多执行秒数（1–3600）</text>
      <input class="field__input" type="number" :value="seconds" :disabled="locked" @input="consentChangedBudget(inputValue($event), 'seconds')" />
    </view>
    <view class="field">
      <text class="field__label">模型预算 USD（0–10，最多 6 位小数）</text>
      <input class="field__input" type="digit" :value="cost" :disabled="locked" @input="consentChangedBudget(inputValue($event), 'cost')" />
    </view>
    <ActionButton
      :label="pendingStart === null ? '启动任务' : '核对并重试同次启动'"
      variant="primary"
      block
      :disabled="locked"
      @tap="start"
    />
    <text v-if="pendingStart !== null" class="warn">
      启动结果尚未确认；重试使用相同请求标识。更改输入将创建新的请求。
    </text>

    <template v-if="run">
      <text class="section-title">执行 #{{ run.id }} · {{ agentLabel(run.status) }}</text>
      <ActionButton label="刷新运行状态" :disabled="locked" @tap="refresh" />
      <FactLine label="流程 / 当前节点" :value="`${agentLabel(run.template)} / ${agentLabel(run.next_node)}`" />
      <FactLine label="来源 / 修订号" :value="`${labelOf(sourceLabels, run.source_status)} / ${run.source_revision}`" />
      <FactLine label="状态说明" :value="agentReason(run.reason)" />
      <FactLine
        label="保存范围"
        :value="`${labelOf(importIdentities, run.input?.scope?.data_identity)} · ${labelOf(importChannels, run.input?.scope?.channel)} · ${run.input?.scope?.currency ?? '未知'}`"
      />
      <FactLine
        label="时间窗"
        :value="`${businessTimeText(run.input?.scope?.start_at ?? '', `${run.input?.scope?.timezone ?? zone}`)} 至 ${businessTimeText(run.input?.scope?.end_at ?? '', `${run.input?.scope?.timezone ?? zone}`)}（结束不含，${run.input?.scope?.timezone ?? '未知'}）`"
      />
      <FactLine label="目标" :value="run.input?.goal" />
      <FactLine label="商品 / 消息" :value="`#${run.input?.product_id ?? '无'} / #${run.input?.message_id ?? '无'}`" />
      <FactLine
        label="步数 / 秒数"
        :value="`${run.steps_used} / ${run.budget.max_steps} 步；${run.elapsed_ms} ms / ${run.budget.max_seconds} 秒`"
      />
      <FactLine
        label="USD 已用 / 预留 / 总预算"
        :value="`${run.spent_usd} / ${run.reserved_usd} / ${run.budget.max_cost_usd}`"
      />
      <text class="hint">外部未提交。模型费用按部署费率估算，在途请求取消后仍可能计费。</text>

      <text class="section-title">步骤进度</text>
      <view v-for="step in run.steps" :key="step.id" class="card">
        <text class="card__title">{{ agentLabel(step.node) }} · {{ agentLabel(step.status) }}</text>
        <text class="hint">
          {{ step.skill }} v{{ step.skill_version }} · {{ step.duration_ms }} ms
        </text>
        <text class="hint">{{ agentReason(step.reason) }}</text>
        <text class="hint">{{ businessTimeText(step.created_at, zone) }}</text>
      </view>

      <template v-if="run.status === 'waiting_approval'">
        <text class="section-title">审批当前内部写入 · R1 · 0 USD</text>
        <text class="hint">{{ approvalText(run.next_node) }}</text>
        <text v-if="run.template === 'margin_review'" class="hint">
          {{
            run.next_node === 'analysis_todo'
              ? '本次批准只保存分析和核对待办。存在独立内容建议时，后续会再次请求批准。'
              : '本次批准保存独立内容草稿；之前已保存的分析保留。'
          }}
        </text>
        <view class="row">
          <ActionButton
            label="已核对，批准当前节点"
            variant="primary"
            :disabled="locked || run.source_status !== 'current'"
            @tap="act('approve')"
          />
          <ActionButton label="拒绝当前节点" :disabled="locked" @tap="act('reject')" />
        </view>
      </template>

      <view class="row">
        <ActionButton
          v-if="run.status === 'ready'"
          :label="run.reason === 'temporary_read_failure' ? '重试安全读取步骤' : '继续执行'"
          variant="primary"
          :disabled="locked"
          @tap="act('advance')"
        />
        <ActionButton v-if="['ready', 'running'].includes(run.status)" label="暂停" :disabled="controlling" @tap="act('pause')" />
        <ActionButton
          v-if="['paused', 'waiting_configuration'].includes(run.status)"
          label="调整预算并恢复"
          :disabled="locked"
          @tap="resumeRun"
        />
        <ActionButton
          v-if="['ready', 'running', 'paused', 'waiting_configuration', 'waiting_approval', 'waiting_input'].includes(run.status)"
          label="取消任务"
          :disabled="controlling"
          @tap="act('cancel')"
        />
        <ActionButton
          label="按此范围重新填写"
          :disabled="locked || run.input === null"
          @tap="restoreInput"
        />
      </view>

      <ActionButton
        v-for="record in recordLinks"
        :key="`${record.record_type}:${record.record_id}`"
        :label="`复查${agentLabel(record.record_type)} #${record.record_id}`"
        :disabled="locked"
        @tap="review(record)"
      />
    </template>

    <text class="section-title">执行历史</text>
    <view v-if="history.length === 0 && !busy" class="card">
      <text class="hint">尚无执行记录。</text>
    </view>
    <view v-for="item in history" :key="item.id" class="card" @tap="inspect(item.id)">
      <text class="card__title">#{{ item.id }} · {{ agentLabel(item.template) }}</text>
      <text class="hint">
        {{ agentLabel(item.status) }} · {{ businessTimeText(item.created_at, zone) }}
      </text>
    </view>

    <text class="section-title">技能与模型状态</text>
    <FactLine label="提供方 / 模型" :value="`${model?.provider ?? '未知'} / ${model?.model ?? '未知'}`" />
    <FactLine label="可用状态" :value="agentLabel(model?.status)" />
    <FactLine label="原因" :value="model?.reason" />
    <FactLine
      label="输入 / 输出 USD 每百万 token"
      :value="`${model?.input_usd_per_million ?? '未知'} / ${model?.output_usd_per_million ?? '未知'}`"
    />
    <FactLine label="费用说明" :value="model?.cost_note" />
    <view v-for="skill in skills" :key="skill.name" class="card">
      <text class="card__title">{{ skill.name }} v{{ skill.version }} · {{ skill.risk }}</text>
      <FactLine label="purpose" :value="skill.purpose" />
      <FactLine label="read_scope" :value="skill.read_scope" />
      <FactLine label="write_scope" :value="skill.write_scope" />
      <FactLine label="idempotency" :value="skill.idempotency" />
      <FactLine label="failure_policy" :value="skill.failure_policy" />
      <FactLine label="confirmation" :value="skill.confirmation" />
      <FactLine label="max_attempts" :value="skill.max_attempts" />
      <FactLine label="input_sources" :value="(skill.input_sources ?? []).join('、')" />
      <FactLine label="permissions" :value="(skill.permissions ?? []).join('、')" />
      <FactLine label="tools" :value="(skill.tools ?? []).join('、')" />
      <FactLine label="preconditions" :value="(skill.preconditions ?? []).join('、')" />
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * AI 助手 / B1：启动执行、步骤进度、双审批、分析存档、Listing 草稿。
 * 接口：
 *   GET  /api/shops/{shop_id}/agent/skills      GET /api/shops/{shop_id}/agent/model
 *   POST /api/shops/{shop_id}/agent/runs         GET /api/shops/{shop_id}/agent/runs
 *   GET  /api/shops/{shop_id}/agent/runs/{run_id}
 *   POST /api/shops/{shop_id}/agent/runs/{run_id}（advance / pause / resume / cancel / approve / reject / use_authorization）
 *   GET  /api/shops/{shop_id}/business-rules     GET /api/shops/{shop_id}/listings/products
 *   GET  /api/shops/{shop_id}/support/messages[/{message_id}]
 *   POST /api/shops/{shop_id}/operations/preview
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import ActionButton from '../../ui/ActionButton.vue'
import { apiGet, apiPost, asObject, newRequestId } from '../../core/api'
import {
  businessTimeText,
  isoClock,
  isoDay,
  nowIsoInZone,
  shiftIso,
  zonedIsoFromParts,
} from '../../core/format'
import {
  agentLabels,
  agentReasons,
  importChannels,
  importIdentities,
  labelOf,
  sourceLabels,
} from '../../core/labels'
import { openWorkPath, takePendingIntent } from '../../core/links'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

interface ProductFacts {
  product_id: number
  sku: string
  name: string
  facts: string
  source: { data_identity: string; row_id: number }
  source_channel?: string
}

interface SupportContext {
  message: { id: number; body: string; language: string; channel: string; source: { data_identity: string; row_id: number } }
  orders: Array<{ order_id: string; line_id: string; sku: string; status: string; fulfillment_status: string; source: { row_id: number } }>
  policies: Array<{ id: number; data?: { title?: string } }>
}

interface AgentStep {
  id: number
  node: string
  skill: string
  skill_version: string
  status: string
  reason: string
  duration_ms: number
  created_at: string
}

interface AgentRun {
  id: number
  shop_id: number
  template: string
  status: string
  reason: string
  version: number
  next_node: string
  source_status: string
  source_revision: number
  input: {
    template?: string
    goal?: string
    product_id?: number | null
    message_id?: number | null
    scope: Record<string, string | number>
  } | null
  result: Record<string, unknown> | null
  steps_used: number
  elapsed_ms: number
  budget: { max_steps: number; max_seconds: number; max_cost_usd: string }
  spent_usd: string
  reserved_usd: string
  model_status: string
  created_at: string
  steps: AgentStep[]
}

interface ModelStatus {
  status: string
  provider: string
  model: string
  reason: string
  input_usd_per_million: string | null
  output_usd_per_million: string | null
  cost_note: string
}

interface Skill {
  name: string
  version: string
  purpose: string
  read_scope: string
  write_scope: string
  idempotency: string
  failure_policy: string
  confirmation: string
  max_attempts: number
  risk: string
  input_sources?: string[]
  permissions?: string[]
  tools?: string[]
  preconditions?: string[]
}

interface OperationContext {
  preview: {
    source_revision: number
    branches: Array<{ name: string; status: string; count: number; reason: string }>
    findings: Array<{ kind: string }>
  }
  preview_hash: string
}

const templateOptions = [
  { key: 'daily', label: '今日运营：检查与异常候选' },
  { key: 'daily_model', label: 'AI 今日运营：检查与解释' },
  { key: 'analysis', label: '销售与已知毛利' },
  { key: 'margin_review', label: 'B1：最近 7 天低毛利复核' },
  { key: 'question', label: 'AI 经营问数' },
  { key: 'listing', label: '商品事实与 Listing 草稿' },
  { key: 'listing_model', label: 'AI Listing 候选' },
  { key: 'support', label: '客服人工接管草稿' },
  { key: 'support_model', label: 'AI 客服候选' },
  { key: 'natural', label: '自然语言目标' },
]

const costModes = [
  { key: 'seller_history', label: '卖家确认的订单行历史成本' },
  { key: 'current_estimate', label: '当前商品成本回推估算' },
]

const dataNotices: Record<string, string> = {
  natural: '目标原文将发送给配置的模型，用于识别任务意图。',
  question: '目标原文、范围、匿名聚合指标、费用缺口及最多 20 个匿名 SKU 指标会发送；正常流程需两次模型请求。',
  daily_model: '目标原文、范围、分支名称/状态/行数和四类候选数量会发送。',
  listing_model: '目标、商品名称与全部参数会发送给模型，请核对原文中的信息。',
  support_model: '目标、消息原文及语言、选中政策全文/主题/核对状态和订单关联核验状态会发送。原文中的姓名、地址等也会随正文发送。',
}

const template = ref('daily')
const costMode = ref('seller_history')
const goal = ref('')
const search = ref('')
const steps = ref('12')
const seconds = ref('120')
const cost = ref('0')
const identity = ref('user_import')
const channel = ref('generic')
const zone = ref(shopTimezone())
const currency = ref(state.shops.find((shop) => shop.id === state.shopId)?.currency ?? 'USD')
const startDay = ref('')
const startClock = ref('00:00')
const endDay = ref('')
const endClock = ref('00:00')
const quantity = ref('1')
const margin = ref('20')
const age = ref('24')
const rule = ref<{ version: number; active: boolean } | null>(null)
const skills = ref<Skill[]>([])
const model = ref<ModelStatus | null>(null)
const history = ref<AgentRun[]>([])
const run = ref<AgentRun | null>(null)
const products = ref<ProductFacts[]>([])
const messages = ref<Array<{ id: number; message_id: string; body: string; channel: string; source: { data_identity: string } }>>([])
const product = ref<ProductFacts | null>(null)
const supportContext = ref<SupportContext | null>(null)
const operationContext = ref<OperationContext | null>(null)
const orderVerified = ref(false)
const policyIds = ref<number[]>([])
const allowModel = ref(false)
const allowData = ref(false)
const pendingStart = ref<Record<string, unknown> | null>(null)
const productOffset = ref(0)
const messageOffset = ref(0)
const driving = ref(false)
const controlling = ref(false)
const busy = ref(false)
const error = ref('')
const successText = ref('')
const ready = ref(false)

const locked = computed(() => busy.value || controlling.value)
const useModel = computed(() =>
  ['natural', 'question', 'listing_model', 'support_model', 'daily_model'].includes(template.value),
)
const needsObject = computed(() =>
  ['listing', 'listing_model', 'support', 'support_model', 'natural', 'margin_review'].includes(template.value),
)
const needsProduct = computed(
  () => needsObject.value && !['support', 'support_model'].includes(template.value),
)
const needsMessage = computed(
  () => needsObject.value && !['listing', 'listing_model', 'margin_review'].includes(template.value),
)
const templateIndex = computed(() => Math.max(0, templateOptions.findIndex((item) => item.key === template.value)))
const costModeIndex = computed(() => Math.max(0, costModes.findIndex((item) => item.key === costMode.value)))
const dataNotice = computed(() => dataNotices[template.value] ?? '')
const scopeFields = computed(() => [
  { key: 'identity', label: '数据身份', options: optionsOf(importIdentities), index: indexOf(importIdentities, identity.value) },
  { key: 'channel', label: '渠道', options: optionsOf(importChannels), index: indexOf(importChannels, channel.value) },
])
const productOptions = computed(() => [
  { key: '', label: '未选择' },
  ...products.value
    .filter((item) => item.source?.data_identity === identity.value)
    .map((item) => ({ key: `${item.product_id}`, label: `${item.sku} · ${item.name}` })),
])
const productIndex = computed(() => {
  const index = productOptions.value.findIndex((item) => item.key === `${product.value?.product_id ?? ''}`)
  return index < 0 ? 0 : index
})
const messageOptions = computed(() => [
  { key: '', label: '未选择' },
  ...messages.value
    .filter((item) => item.source?.data_identity === identity.value && item.channel === channel.value)
    .map((item) => ({ key: `${item.id}`, label: `${item.message_id} · ${item.body}` })),
])
const messageIndex = computed(() => {
  const index = messageOptions.value.findIndex((item) => item.key === `${supportContext.value?.message.id ?? ''}`)
  return index < 0 ? 0 : index
})
const recordLinks = computed(() => {
  const found = new Map<string, { record_type: string; record_id: number }>()
  const records = [run.value?.result, ...(run.value?.steps ?? []).filter((step) => step.node === 'verify')]
  for (const record of records) {
    const value = asObject<{ record_type?: string; record_id?: number }>(record)
    if (value?.record_type !== undefined && value.record_id !== undefined) {
      found.set(`${value.record_type}:${value.record_id}`, {
        record_type: value.record_type,
        record_id: value.record_id,
      })
    }
  }
  return [...found.values()].filter((item) => ['listing', 'support'].includes(item.record_type))
})

function optionsOf(map: Record<string, string>): Array<{ key: string; label: string }> {
  return Object.entries(map).map(([key, label]) => ({ key, label }))
}

function indexOf(map: Record<string, string>, key: string): number {
  const index = Object.keys(map).indexOf(key)
  return index < 0 ? 0 : index
}

function agentLabel(value: unknown): string {
  return labelOf(agentLabels, value)
}

function agentReason(value: unknown): string {
  if (value === null || value === undefined || `${value}` === '') return '未知'
  return agentReasons[`${value}`] ?? `${value}`
}

function approvalText(node: string): string {
  const table: Record<string, string> = {
    propose_tasks: '保存下列异常为工作台待审批候选。已有候选保留处理状态。',
    analysis_todo: '保存当前分析快照，并创建一个销售与已知毛利核对待办。可在分析页完成或重开。',
    listing_draft: '依据完整商品名称和参数保存本地 Listing 模板草稿；进入 Listing 页另行批准生效。',
    listing_candidate: '将下方模型候选保存为待审 Listing；进入 Listing 页另行批准生效。',
    support_candidate: '保存下方回复候选及人工接管原因；进入客服页编辑、审阅或存档。',
    support_draft: '保存未核验订单、未选择政策的人工接管草稿；进入客服页继续核对。',
  }
  return table[node] ?? '请核对本节点的对象、依据和影响。'
}

function success(text: string): void {
  successText.value = text
  void Taro.showToast({ title: text, icon: 'none' })
}

function resetConsent(): void {
  allowModel.value = false
  allowData.value = false
  pendingStart.value = null
  if (product.value !== null && product.value.source?.data_identity !== identity.value) {
    product.value = null
  }
  if (
    supportContext.value !== null &&
    (supportContext.value.message.source?.data_identity !== identity.value ||
      supportContext.value.message.channel !== channel.value)
  ) {
    supportContext.value = null
    policyIds.value = []
    orderVerified.value = false
  }
}

function setTemplate(event: { detail: { value: string } }): void {
  template.value = templateOptions[Number(event.detail.value)]?.key ?? 'daily'
  operationContext.value = null
  resetConsent()
}

function setCostMode(event: { detail: { value: string } }): void {
  costMode.value = costModes[Number(event.detail.value)]?.key ?? 'seller_history'
  resetConsent()
}

function setScopeChoice(key: string, value: string): void {
  if (key === 'identity') identity.value = value
  if (key === 'channel') channel.value = value
  rule.value = null
  operationContext.value = null
  resetConsent()
}

function setProduct(event: { detail: { value: string } }): void {
  const key = productOptions.value[Number(event.detail.value)]?.key ?? ''
  resetConsent()
  if (key === '') {
    product.value = null
    return
  }
  void perform(async () => {
    const workspace = asObject<{ product: ProductFacts }>(await apiGet(shopPath(`/listings/products/${key}`)))
    product.value = workspace?.product ?? null
  })
}

function setMessage(event: { detail: { value: string } }): void {
  const key = messageOptions.value[Number(event.detail.value)]?.key ?? ''
  resetConsent()
  orderVerified.value = false
  policyIds.value = []
  if (key === '') {
    supportContext.value = null
    return
  }
  void perform(async () => {
    supportContext.value = asObject<SupportContext>(await apiGet(shopPath(`/support/messages/${key}`)))
  })
}

function togglePolicy(id: number): void {
  if (locked.value) return
  if (policyIds.value.includes(id)) {
    policyIds.value = policyIds.value.filter((item) => item !== id)
  } else if (policyIds.value.length < 10) {
    policyIds.value = [...policyIds.value, id]
  } else {
    error.value = '最多选择 10 份政策。'
    return
  }
  allowModel.value = false
  pendingStart.value = null
}

function toggleAllowModel(): void {
  if (locked.value) return
  allowModel.value = !allowModel.value
  pendingStart.value = null
}

function toggleAllowData(): void {
  if (locked.value) return
  if (template.value === 'daily_model' && operationContext.value === null) return
  allowData.value = !allowData.value
  pendingStart.value = null
}

function consentChanged(value: string): void {
  goal.value = value
  resetConsent()
}

function consentChangedBudget(value: string, field: 'steps' | 'seconds' | 'cost'): void {
  if (field === 'steps') steps.value = value
  if (field === 'seconds') seconds.value = value
  if (field === 'cost') cost.value = value
  resetConsent()
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  const intent = takePendingIntent('/pages/agent/index')
  if (intent?.mode && templateOptions.some((item) => item.key === intent.mode)) {
    template.value = intent.mode
  }
  if (intent?.identity && Object.keys(importIdentities).includes(intent.identity)) {
    identity.value = intent.identity
  }
  const wanted = Number(intent?.product ?? '')
  if (Number.isFinite(wanted) && wanted > 0) intentProduct.value = wanted
  await load(true)
})

async function load(initial = false): Promise<void> {
  if (!ready.value) return
  initializeWindow()
  const message = await perform(async () => {
    const [skillValue, modelValue, runValue] = await Promise.all([
      apiGet<Skill[]>(shopPath('/agent/skills')),
      apiGet<ModelStatus>(shopPath('/agent/model')),
      apiGet<AgentRun[]>(shopPath('/agent/runs')),
    ])
    skills.value = Array.isArray(skillValue) ? skillValue : []
    model.value = asObject<ModelStatus>(modelValue)
    history.value = Array.isArray(runValue) ? runValue : []
    if (initial && intentProduct.value !== null) {
      const workspace = asObject<{ product: ProductFacts }>(
        await apiGet(shopPath(`/listings/products/${intentProduct.value}`)),
      )
      product.value = workspace?.product ?? null
    }
  })
  error.value = message
}

const intentProduct = ref<number | null>(null)

function initializeWindow(): void {
  if (endDay.value !== '') return
  const currentZone = zone.value
  const now = nowIsoInZone(currentZone) ?? ''
  endDay.value = isoDay(now, currentZone) ?? ''
  endClock.value = isoClock(now, currentZone) ?? '00:00'
  const from = shiftIso(now, -7, currentZone) ?? ''
  startDay.value = isoDay(from, currentZone) ?? ''
  startClock.value = isoClock(from, currentZone) ?? '00:00'
}

/** 读取当前范围的经营规则（内层实现，便于在 perform 内复用）。 */
async function fetchRule(): Promise<void> {
  const value = asObject<{ version: number; active: boolean; values: Record<string, number> }>(
    await apiGet(shopPath('/business-rules'), { channel: channel.value, data_identity: identity.value }),
  )
  if (value === null) throw new Error('经营规则响应无法读取，请重试。')
  rule.value = { version: value.version, active: value.active === true }
  const values = value.values ?? {}
  if (values.max_age_hours !== undefined) age.value = `${values.max_age_hours}`
  if (values.min_quantity !== undefined) quantity.value = `${values.min_quantity}`
  if (values.max_margin_percent !== undefined) margin.value = `${values.max_margin_percent}`
}

async function readRule(): Promise<void> {
  const message = await perform(fetchRule)
  error.value = message
}

async function readOptions(moreProducts = false, moreMessages = false): Promise<void> {
  const message = await perform(async () => {
    if (moreProducts) {
      productOffset.value += 50
    } else if (moreMessages) {
      messageOffset.value += 50
    } else {
      productOffset.value = 0
      messageOffset.value = 0
    }
    if (!moreMessages) {
      const rows = await apiGet<ProductFacts[]>(shopPath('/listings/products'), {
        q: search.value.trim(),
        offset: productOffset.value,
      })
      products.value = Array.isArray(rows) ? rows : []
    }
    if (!moreProducts) {
      const rows = await apiGet<Array<{ id: number; message_id: string; body: string; channel: string; source: { data_identity: string } }>>(
        shopPath('/support/messages'),
        { q: search.value.trim(), offset: messageOffset.value },
      )
      messages.value = Array.isArray(rows) ? rows : []
    }
    resetConsent()
  })
  error.value = message
}

async function previewOperations(): Promise<void> {
  const message = await perform(async () => {
    operationContext.value = asObject<OperationContext>(
      await apiPost(shopPath('/operations/preview'), scopePayload()),
    )
    resetConsent()
  })
  error.value = message
}

function isoOf(day: string, clock: string): string {
  const value = zonedIsoFromParts(day, clock, zone.value)
  if (value === null) throw new Error('时间无效或在该时区不存在，请重新选择日期与时间。')
  return value
}

function scopePayload(): Record<string, unknown> {
  const end = isoOf(endDay.value, endClock.value)
  const start =
    template.value === 'margin_review'
      ? shiftIso(end, -7, zone.value)
      : isoOf(startDay.value, startClock.value)
  if (start === null) throw new Error('无法按当前时区计算精确 7 天窗口。')
  const span = Date.parse(end) - Date.parse(start)
  if (!(span > 0) || span > 366 * 86400000) {
    throw new Error('统计时间窗须大于 0 且不超过 366 天。')
  }
  const minQuantity = Number(quantity.value)
  const maxAge = Number(age.value)
  if (!Number.isInteger(minQuantity) || minQuantity < 1 || minQuantity > 1000000) {
    throw new Error('最低销量须为正整数，库存有效期须为 1–720 小时。')
  }
  if (!Number.isInteger(maxAge) || maxAge < 1 || maxAge > 720) {
    throw new Error('最低销量须为正整数，库存有效期须为 1–720 小时。')
  }
  if (!/^-?\d+(\.\d{1,2})?$/.test(margin.value.trim())) {
    throw new Error('请填写有效的毛利百分比。')
  }
  const marginValue = Number(margin.value)
  if (marginValue < -1000 || marginValue > 100) {
    throw new Error('毛利百分比须为 -1000 至 100。')
  }
  if (rule.value === null) throw new Error('请先读取当前范围的经营规则。')
  return {
    start_at: start,
    end_at: end,
    timezone: zone.value.trim(),
    currency: currency.value.trim().toUpperCase(),
    data_identity: identity.value,
    channel: channel.value,
    intent: 'low_margin',
    cost_mode: 'current_estimate',
    min_quantity: minQuantity,
    max_margin_percent: margin.value.trim(),
    max_age_hours: maxAge,
    rule_revision_id: rule.value.version,
  }
}

function budgetPayload(): Record<string, unknown> {
  const maxSteps = Number(steps.value)
  const maxSeconds = Number(seconds.value)
  if (
    !Number.isInteger(maxSteps) || maxSteps < 1 || maxSteps > 100 ||
    !Number.isInteger(maxSeconds) || maxSeconds < 1 || maxSeconds > 3600 ||
    !/^\d+(\.\d{1,6})?$/.test(cost.value.trim()) || Number(cost.value) > 10
  ) {
    throw new Error('预算须为 1–100 步、1–3600 秒、0–10 USD（最多 6 位小数）。')
  }
  return { max_steps: maxSteps, max_seconds: maxSeconds, max_cost_usd: cost.value.trim() }
}

function startPayload(): Record<string, unknown> {
  if (useModel.value && (goal.value.trim() === '' || goal.value.length > 500 || !allowModel.value)) {
    throw new Error('请填写 1–500 字目标，并核对本次模型数据授权。')
  }
  if (useModel.value && template.value !== 'natural' && !allowData.value) {
    throw new Error('请核对本次业务数据发送范围。')
  }
  if (needsProduct.value && product.value === null) throw new Error('请选择商品。')
  if (needsMessage.value && supportContext.value === null) throw new Error('请选择消息。')
  if (product.value !== null && product.value.source?.data_identity !== identity.value) {
    throw new Error('商品不属于当前数据身份或复核渠道，请重新选择。')
  }
  if (
    supportContext.value !== null &&
    (supportContext.value.message.source?.data_identity !== identity.value ||
      supportContext.value.message.channel !== channel.value)
  ) {
    throw new Error('消息身份或渠道不匹配。')
  }
  if (template.value === 'daily_model' && operationContext.value === null) {
    throw new Error('请先预览本次运营数据。')
  }
  if (policyIds.value.length > 10) throw new Error('最多选择 10 份政策。')
  return {
    request_id: newRequestId(),
    template: template.value,
    margin_cost_mode: costMode.value,
    scope: scopePayload(),
    goal: goal.value.trim(),
    product_id: product.value?.product_id ?? null,
    message_id: supportContext.value?.message.id ?? null,
    allow_model: useModel.value && allowModel.value,
    allow_analysis_data: template.value === 'question' && allowData.value,
    allow_listing_data: template.value === 'listing_model' && allowData.value,
    allow_support_data: template.value === 'support_model' && allowData.value,
    allow_operation_data: template.value === 'daily_model' && allowData.value,
    expected_operation_hash: operationContext.value?.preview_hash ?? null,
    expected_product_source_row_id:
      template.value === 'listing_model' ? product.value?.source?.row_id ?? null : null,
    support_context:
      template.value === 'support_model' && supportContext.value !== null
        ? {
            expected_source_row_id: supportContext.value.message.source?.row_id,
            expected_order_row_ids: orderVerified.value
              ? supportContext.value.orders.map((order) => order.source.row_id)
              : [],
            order_verified: orderVerified.value,
            policy_ids: policyIds.value,
          }
        : null,
    budget: budgetPayload(),
  }
}

/** 连续推进 ready 状态，直到等待审批、完成或达到上限。 */
async function drive(): Promise<void> {
  driving.value = true
  try {
    for (let index = 0; index < 100 && driving.value && run.value?.status === 'ready'; index += 1) {
      const current = run.value
      if (current === null) break
      const value = asObject<AgentRun>(
        await apiPost(shopPath(`/agent/runs/${current.id}`), {
          version: current.version,
          action: 'advance',
        }),
      )
      if (value !== null) accept(value)
    }
  } finally {
    driving.value = false
  }
}

function accept(value: AgentRun): void {
  const current = run.value
  if (
    current === null ||
    (current.id === value.id && value.version >= current.version)
  ) {
    run.value = value
  }
}

async function start(): Promise<void> {
  if (locked.value) return
  const message = await perform(async () => {
    if (pendingStart.value === null) pendingStart.value = startPayload()
    try {
      const value = asObject<AgentRun>(await apiPost(shopPath('/agent/runs'), pendingStart.value))
      if (value !== null) {
        run.value = value
        pendingStart.value = null
      }
      await drive()
      await refresh()
    } catch (failure) {
      // 4xx 表示后端已明确拒绝，重试无意义；保留未知结果时才复用同一 request_id。
      if (failure instanceof Error && /4\d\d/.test(failure.message)) pendingStart.value = null
      throw failure
    }
  })
  error.value = message
}

async function act(action: string): Promise<void> {
  const current = run.value
  if (current === null || controlling.value) return
  if (busy.value && !['pause', 'cancel'].includes(action)) return
  controlling.value = true
  driving.value = false
  const message = await perform(async () => {
    const latest =
      ['pause', 'cancel'].includes(action)
        ? asObject<AgentRun>(await apiGet(shopPath(`/agent/runs/${current.id}`)))
        : current
    if (latest === null) throw new Error('执行记录无法读取，请刷新后重试。')
    const value = asObject<AgentRun>(
      await apiPost(shopPath(`/agent/runs/${latest.id}`), {
        version: latest.version,
        action,
      }),
    )
    if (value !== null) accept(value)
    if (['approve', 'resume', 'advance', 'use_authorization'].includes(action)) {
      await drive()
    }
  })
  controlling.value = false
  if (message === '') {
    error.value = ''
    await refresh()
  } else {
    error.value = message
    await refresh()
  }
}

async function resumeRun(): Promise<void> {
  const current = run.value
  if (current === null) return
  const budget = current.budget
  const modal = await Taro.showModal({
    title: '恢复任务总预算',
    content: `总预算包含已用费用。当前为 ${budget.max_steps} 步 / ${budget.max_seconds} 秒 / ${budget.max_cost_usd} USD。被丢弃的模型结果恢复时可能重新请求。`,
    confirmText: '按当前输入恢复',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  const message = await perform(async () => {
    const next = budgetPayload()
    if (
      Number(next.max_steps) < budget.max_steps ||
      Number(next.max_seconds) < budget.max_seconds ||
      Number(next.max_cost_usd) < Number(budget.max_cost_usd)
    ) {
      throw new Error('恢复预算不得低于当前总预算（含已用费用）。')
    }
    const value = asObject<AgentRun>(
      await apiPost(shopPath(`/agent/runs/${current.id}`), {
        version: current.version,
        action: 'resume',
        budget: next,
      }),
    )
    if (value !== null) accept(value)
    await drive()
  })
  if (message === '') {
    error.value = ''
    await refresh()
  } else {
    error.value = message
  }
}

async function refresh(): Promise<void> {
  const message = await perform(async () => {
    const rows = await apiGet<AgentRun[]>(shopPath('/agent/runs'))
    history.value = Array.isArray(rows) ? rows : []
    if (run.value !== null) {
      const value = asObject<AgentRun>(await apiGet(shopPath(`/agent/runs/${run.value.id}`)))
      if (value !== null) accept(value)
    }
  })
  if (message !== '') error.value = message
}

async function inspect(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<AgentRun>(await apiGet(shopPath(`/agent/runs/${id}`)))
    if (value !== null) run.value = value
  })
  error.value = message
}

async function restoreInput(): Promise<void> {
  const input = run.value?.input
  if (!input) return
  const message = await perform(async () => {
    template.value = `${input.template ?? 'daily'}`
    goal.value = `${input.goal ?? ''}`
    costMode.value = `${(input as unknown as { margin_cost_mode?: string }).margin_cost_mode ?? 'seller_history'}`
    const scope = input.scope ?? {}
    identity.value = `${scope.data_identity ?? 'user_import'}`
    channel.value = `${scope.channel ?? 'generic'}`
    zone.value = `${scope.timezone ?? zone.value}`
    currency.value = `${scope.currency ?? currency.value}`
    quantity.value = `${scope.min_quantity ?? 1}`
    margin.value = `${scope.max_margin_percent ?? 20}`
    age.value = `${scope.max_age_hours ?? 24}`
    const start = `${scope.start_at ?? ''}`
    const end = `${scope.end_at ?? ''}`
    startDay.value = isoDay(start, zone.value) ?? startDay.value
    startClock.value = isoClock(start, zone.value) ?? startClock.value
    endDay.value = isoDay(end, zone.value) ?? endDay.value
    endClock.value = isoClock(end, zone.value) ?? endClock.value
    product.value = null
    supportContext.value = null
    operationContext.value = null
    policyIds.value = []
    orderVerified.value = false
    rule.value = null
    await fetchRule()
  })
  if (message === '') success('已按历史输入填入新任务表单并读取当前规则，请重新核对数据与授权。')
  else error.value = message
}

function review(record: { record_type: string; record_id: number }): void {
  const target = record.record_type === 'listing' ? '/listings' : '/support'
  void openWorkPath(target, { [record.record_type === 'listing' ? 'listing' : 'draft']: `${record.record_id}` })
}
</script>
