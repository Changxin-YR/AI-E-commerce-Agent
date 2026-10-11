<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { requestId, queryString } from '../../services/task-policy'
import { agentLabels, agentReasons } from '../../services/agent-types'
import type {
  AgentAction,
  AgentInput,
  AgentRun,
  AgentTemplate,
  ModelStatus,
  SkillDefinition,
} from '../../services/agent-types'
import {
  agentActions,
  prepareAgentInput,
  reviewedRecords,
} from '../../services/agent-policy'
import type { ProductFacts } from '../../services/listing-types'
import type {
  MessageFacts,
  SupportWorkspace,
} from '../../services/support-types'
import type { OperationContext } from '../../services/operation-types'
import { ApiError } from '../../services/client'
import AppliedRules from '../../components/AppliedRules.vue'
import AgentResult from '../../components/AgentResult.vue'
import AgentEvidence from '../../components/AgentEvidence.vue'
import InternalAuthorizations from '../../components/InternalAuthorizations.vue'
import SourceList from '../../components/SourceList.vue'

function checked(event: unknown) {
  return Boolean((event as { detail: { value: boolean } }).detail.value)
}
const templates: AgentTemplate[] = [
  'daily',
  'analysis',
  'margin_review',
  'listing',
  'support',
  'natural',
  'question',
  'listing_model',
  'support_model',
  'daily_model',
]
const now = Date.now()
const form = reactive<AgentInput>({
  request_id: '',
  template: 'daily',
  margin_cost_mode: 'seller_history',
  goal: '',
  product_id: null,
  message_id: null,
  allow_model: false,
  allow_analysis_data: false,
  allow_listing_data: false,
  allow_support_data: false,
  allow_operation_data: false,
  budget: { max_steps: 12, max_seconds: 120, max_cost_usd: '0' },
  scope: {
    start_at: new Date(now - 7 * 86400000).toISOString(),
    end_at: new Date(now).toISOString(),
    timezone: 'Asia/Shanghai',
    currency: 'USD',
    data_identity: 'user_import',
    channel: 'generic',
    intent: 'low_margin',
    min_quantity: 1,
    max_margin_percent: '20',
    max_age_hours: 24,
  },
})
const resumeBudget = reactive({
  max_steps: 12,
  max_seconds: 120,
  max_cost_usd: '0',
})
const run = ref<AgentRun>(),
  runs = ref<AgentRun[]>([]),
  skills = ref<SkillDefinition[]>([]),
  model = ref<ModelStatus>()
const products = ref<ProductFacts[]>([]),
  messages = ref<MessageFacts[]>([]),
  support = ref<SupportWorkspace>(),
  operation = ref<OperationContext>()
const rulesPending = ref(true),
  activeRule = ref(false)
function applyRules(rule: {
  version: number
  active: boolean
  values: {
    max_age_hours: number
    min_quantity: number
    max_margin_percent: string
  }
}) {
  form.scope.rule_revision_id = rule.version
  activeRule.value = rule.active
  form.scope.max_age_hours = rule.values.max_age_hours
  form.scope.min_quantity = rule.values.min_quantity
  form.scope.max_margin_percent = rule.values.max_margin_percent
}
const search = ref(''),
  productOffset = ref(0),
  messageOffset = ref(0),
  orderVerified = ref(false),
  policyIds = ref<number[]>([])
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  reviewed = ref(false),
  pending = ref<AgentInput>(),
  unknownAction = ref(false)
const query = ref<Record<string, string>>({})
let alive = true
let epoch = 0
const base = () => `/shops/${account.shopId}/agent`
const product = computed(() =>
  products.value.find((p) => p.product_id === form.product_id),
)
const actions = computed(() => (run.value ? agentActions(run.value) : []))
const records = computed(() => (run.value ? reviewedRecords(run.value) : []))
const labels: Record<string, string> = {
  advance: '推进一个节点',
  pause: '暂停',
  resume: '确认预算并恢复',
  cancel: '取消任务',
  approve: '批准当前节点',
  reject: '拒绝当前节点',
}
function consentOff() {
  form.allow_model = false
  form.allow_analysis_data = false
  form.allow_listing_data = false
  form.allow_support_data = false
  form.allow_operation_data = false
}
watch(
  () => [
    form.template,
    form.goal,
    form.product_id,
    form.message_id,
    JSON.stringify(form.scope),
    JSON.stringify(form.budget),
    form.margin_cost_mode,
    orderVerified.value,
    policyIds.value.join(','),
  ],
  consentOff,
  { flush: 'sync' },
)
watch(
  () => JSON.stringify(form.scope),
  () => {
    operation.value = undefined
    form.expected_operation_hash = null
  },
)
watch(
  () => [run.value?.id, run.value?.version],
  () => {
    reviewed.value = false
    if (run.value) Object.assign(resumeBudget, run.value.budget)
  },
)
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    epoch++
    run.value = undefined
    runs.value = []
    skills.value = []
    model.value = undefined
    pending.value = undefined
    unknownAction.value = false
    products.value = []
    messages.value = []
    support.value = undefined
    operation.value = undefined
    form.product_id = null
    form.message_id = null
    form.authorization_id = null
    consentOff()
    query.value = {}
    error.value = ''
    notice.value = ''
  },
)
useLoad((params) => {
  query.value = params as Record<string, string>
})
useUnload(() => {
  alive = false
  epoch++
})
async function perform(work: () => Promise<void>) {
  if (busy.value) return
  if (!account.session || !account.shopId) {
    error.value = '请先登录并选择店铺。'
    return
  }
  busy.value = true
  error.value = ''
  notice.value = ''
  const token = epoch
  try {
    await work()
  } catch (cause) {
    if (alive && token === epoch)
      error.value =
        cause instanceof Error ? cause.message : '请求失败，请回读核对。'
  } finally {
    busy.value = false
  }
}
function accept(value: AgentRun) {
  if (alive && account.shopId === value.shop_id) run.value = value
}
async function readRun(id: number) {
  accept(await api.request<AgentRun>(`${base()}/runs/${id}`))
  unknownAction.value = false
}
async function history() {
  runs.value = await api.request<AgentRun[]>(`${base()}/runs`)
}
async function refresh() {
  await perform(async () => {
    await history()
    if (run.value) await readRun(run.value.id)
  })
}
async function inspect(id: number) {
  await perform(async () => {
    await readRun(id)
  })
}
async function options(more = false) {
  await perform(async () => {
    const po = more ? productOffset.value + 50 : 0,
      mo = more ? messageOffset.value + 50 : 0
    const [p, m] = await Promise.all([
      api.request<ProductFacts[]>(
        `/shops/${account.shopId}/listings/products?${queryString({ q: search.value, offset: po })}`,
      ),
      api.request<MessageFacts[]>(
        `/shops/${account.shopId}/support/messages?${queryString({ q: search.value, offset: mo })}`,
      ),
    ])
    products.value = more ? [...products.value, ...p] : p
    messages.value = more ? [...messages.value, ...m] : m
    productOffset.value = po
    messageOffset.value = mo
    if (!more) {
      form.product_id = null
      form.message_id = null
      support.value = undefined
    }
  })
}
async function chooseMessage(id: number) {
  await perform(async () => {
    support.value = undefined
    orderVerified.value = false
    policyIds.value = []
    form.message_id = id
    support.value = await api.request<SupportWorkspace>(
      `/shops/${account.shopId}/support/messages/${id}`,
    )
  })
}
function togglePolicy(id: number, value: boolean) {
  policyIds.value = value
    ? [...policyIds.value, id]
    : policyIds.value.filter((item) => item !== id)
}
async function operationPreview() {
  await perform(async () => {
    consentOff()
    operation.value = await api.request<OperationContext>(
      `/shops/${account.shopId}/operations/preview`,
      'POST',
      form.scope,
    )
    form.expected_operation_hash = operation.value.preview_hash
  })
}
async function submit(recover = false) {
  await perform(async () => {
    if (!recover) {
      if (rulesPending.value) throw new Error('请先读取当前经营规则。')
      if (pending.value)
        throw new Error('上一启动结果尚未核对，请先使用同次请求恢复。')
      const input = prepareAgentInput({
        ...form,
        request_id: requestId(),
        expected_product_source_row_id: product.value?.source.row_id,
        support_context: support.value
          ? {
              expected_source_row_id: support.value.message.source.row_id,
              expected_order_row_ids: orderVerified.value
                ? support.value.orders.map((o) => o.source.row_id)
                : [],
              order_verified: orderVerified.value,
              policy_ids: policyIds.value,
            }
          : null,
      })
      if (
        input.product_id &&
        product.value?.source.data_identity !== input.scope.data_identity
      )
        throw new Error('商品与所选数据身份不一致。')
      if (
        input.message_id &&
        (support.value?.message.source.data_identity !==
          input.scope.data_identity ||
          support.value?.message.channel !== input.scope.channel)
      )
        throw new Error('消息与所选身份或渠道不一致。')
      pending.value = input
    }
    if (!pending.value) return
    let created: AgentRun
    try {
      created = await api.request<AgentRun>(
        `${base()}/runs`,
        'POST',
        pending.value,
      )
    } catch (cause) {
      if (
        cause instanceof ApiError &&
        cause.status >= 400 &&
        cause.status < 500 &&
        cause.status !== 408
      )
        pending.value = undefined
      throw cause
    }
    accept(created)
    await readRun(created.id)
    pending.value = undefined
    await history()
    notice.value = '启动结果已回读。请逐节点推进。'
  })
}
async function act(action: AgentAction, grant?: number) {
  await perform(async () => {
    const token = epoch
    const current = run.value
    if (!current || unknownAction.value) return
    if (action !== 'use_authorization' && !actions.value.includes(action))
      return
    if (action === 'approve' && !reviewed.value)
      throw new Error('请先核对当前节点全部依据。')
    if (['cancel', 'reject'].includes(action)) {
      const answer = await Taro.showModal({
        title: labels[action],
        content: `仅处理任务 #${current.id} 的当前节点 ${current.next_node}，此前已保存结果保留。`,
      })
      if (!answer.confirm || token !== epoch || !alive) return
    }
    unknownAction.value = true
    const updated = await api.request<AgentRun>(
      `${base()}/runs/${current.id}`,
      'POST',
      {
        version: current.version,
        action,
        ...(action === 'resume' ? { budget: { ...resumeBudget } } : {}),
        ...(grant ? { authorization_id: grant } : {}),
      },
    )
    accept(updated)
    await readRun(current.id)
    await history()
  })
}
async function readObjects(
  productId?: number | null,
  messageId?: number | null,
) {
  if (productId) {
    const value = await api.request<{ product: ProductFacts }>(
      `/shops/${account.shopId}/listings/products/${productId}`,
    )
    products.value = [value.product]
    form.product_id = value.product.product_id
    form.scope.data_identity =
      value.product.source.data_identity === 'synthetic'
        ? 'synthetic'
        : 'user_import'
  }
  if (messageId) {
    const value = await api.request<SupportWorkspace>(
      `/shops/${account.shopId}/support/messages/${messageId}`,
    )
    support.value = value
    messages.value = [value.message]
    form.message_id = value.message.id
    form.scope.data_identity =
      value.message.source.data_identity === 'synthetic'
        ? 'synthetic'
        : 'user_import'
    form.scope.channel = value.message.channel
    orderVerified.value = false
    policyIds.value = []
  }
}
async function reuseInput() {
  await perform(async () => {
    if (!run.value?.input || pending.value) return
    const value = JSON.parse(JSON.stringify(run.value.input)) as AgentInput
    Object.assign(form, value, {
      request_id: '',
      authorization_id: null,
      expected_operation_hash: null,
      support_context: null,
    })
    consentOff()
    operation.value = undefined
    support.value = undefined
    products.value = []
    messages.value = []
    await readObjects(value.product_id, value.message_id)
    notice.value =
      '已填入原范围并读取当前对象。请刷新经营规则、重新审阅并确认数据许可，再启动新任务。'
  })
}
async function startAuthorized(grant: {
  id: number
  scope: AgentInput['scope']
}) {
  if (pending.value || busy.value) return
  form.template = 'daily'
  Object.assign(form.scope, grant.scope)
  form.authorization_id = grant.id
  form.product_id = null
  form.message_id = null
  form.goal = ''
  consentOff()
  await submit()
  form.authorization_id = null
}
useDidShow(() => {
  void perform(async () => {
    const shop = account.shops.find((s) => s.id === account.shopId)
    if (shop) {
      form.scope.currency = shop.currency
      form.scope.timezone = shop.timezone
    }
    const [registry, status] = await Promise.all([
      api.request<SkillDefinition[]>(`${base()}/skills`),
      api.request<ModelStatus>(`${base()}/model`),
    ])
    skills.value = registry
    model.value = status
    await history()
    if (query.value.shop && Number(query.value.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不同，请从工作台重新打开。')
    const id = Number(query.value.execution || query.value.run || run.value?.id)
    if (id > 0) await readRun(id)
    if (templates.includes(query.value.mode as AgentTemplate))
      form.template = query.value.mode as AgentTemplate
    await readObjects(
      Number(query.value.product) || undefined,
      Number(query.value.message) || undefined,
    )
    query.value = {}
  })
})
</script>
<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow">SOLOOPS · AI 运营</text
      ><text class="title">每一步，都有依据。</text
      ><text class="muted">审批仅针对当前内部写入；外部未提交。</text></view
    >
    <view v-if="error" class="error">{{ error }}</view
    ><view v-if="notice" class="notice">{{ notice }}</view>
    <view v-if="pending" class="card"
      ><text class="label">启动结果待核对</text
      ><text class="hint"
        >请求
        {{
          pending.request_id
        }}；同次恢复保留原始范围和许可，不采用下方修改。</text
      ><button :disabled="busy" @tap="submit(true)">
        以同次请求核对 / 恢复
      </button></view
    >
    <view class="card">
      <text class="section-title">新建运营任务</text
      ><picker
        :range="templates.map((t) => agentLabels[t])"
        @change="form.template = templates[Number($event.detail.value)]!"
        :disabled="busy"
        ><view class="select">{{ agentLabels[form.template] }}</view></picker
      >
      <text class="label">目标（最多500字）</text
      ><textarea
        v-model="form.goal"
        :maxlength="500"
        :disabled="busy"
        placeholder="例如：核对最近7天低毛利商品及独立内容缺项"
      />
      <text class="label">开始 / 结束时间（ISO，含时区）</text
      ><input
        v-model="form.scope.start_at"
        :disabled="busy || form.template === 'margin_review'"
      /><input v-model="form.scope.end_at" :disabled="busy" /><text
        v-if="form.template === 'margin_review'"
        class="hint"
        >B1 自动取结束时间之前精确7天，结束不含；两次审批分别保存分析与
        Listing。</text
      >
      <text class="label">币种 / 业务时区</text
      ><input v-model="form.scope.currency" :disabled="busy" /><input
        v-model="form.scope.timezone"
        :disabled="busy"
      />
      <picker
        :range="['user_import', 'synthetic']"
        :disabled="busy"
        @change="
          form.scope.data_identity = Number($event.detail.value)
            ? 'synthetic'
            : 'user_import'
        "
        ><view class="select"
          >数据身份 {{ form.scope.data_identity }}</view
        ></picker
      >
      <picker
        :range="['generic', 'amazon', 'shopify', 'other']"
        :disabled="busy"
        @change="
          form.scope.channel = ['generic', 'amazon', 'shopify', 'other'][
            Number($event.detail.value)
          ]!
        "
        ><view class="select">渠道 {{ form.scope.channel }}</view></picker
      >
      <AppliedRules
        :scope="form.scope"
        :disabled="busy"
        @pending="rulesPending = $event"
        @loaded="applyRules"
      /><text class="label">最低销量 / 毛利率阈值% / 库存时效小时</text
      ><input
        v-model.number="form.scope.min_quantity"
        type="number"
        :disabled="busy || activeRule"
      /><input
        v-model="form.scope.max_margin_percent"
        type="digit"
        :disabled="busy || activeRule"
      /><input
        v-model.number="form.scope.max_age_hours"
        type="number"
        :disabled="busy || activeRule"
      />
      <picker
        :range="['卖家历史成本', '当前商品成本估算']"
        :disabled="busy"
        @change="
          form.margin_cost_mode = Number($event.detail.value)
            ? 'current_estimate'
            : 'seller_history'
        "
        ><view class="select"
          >B1成本口径
          {{
            form.margin_cost_mode === 'seller_history'
              ? '卖家历史成本'
              : '当前商品成本估算'
          }}</view
        ></picker
      >
      <text class="label">商品或消息</text
      ><input
        v-model="search"
        placeholder="SKU / 消息关键词"
        :disabled="busy"
      /><button :disabled="busy" @tap="options(false)">搜索对象</button
      ><button :disabled="busy" @tap="options(true)">下一批对象</button>
      <view v-for="item in products" :key="item.product_id"
        ><button :disabled="busy" @tap="form.product_id = item.product_id">
          {{ form.product_id === item.product_id ? '✓ ' : '' }}{{ item.sku }} ·
          {{ item.name }} · {{ item.source.data_identity }}
        </button></view
      >
      <view v-if="product"
        ><text class="label">商品事实全文</text
        ><text class="prose">{{ product.facts }}</text
        ><SourceList :sources="[product.source]" :shop-id="account.shopId"
      /></view>
      <view v-for="item in messages" :key="item.id"
        ><button :disabled="busy" @tap="chooseMessage(item.id)">
          {{ form.message_id === item.id ? '✓ ' : '' }}消息
          {{ item.message_id }} · {{ item.language }} · {{ item.channel }}
        </button></view
      >
      <view v-if="support"
        ><text class="label">消息全文</text
        ><text class="prose">{{ support.message.body }}</text
        ><text
          v-for="order in support.orders"
          :key="order.source.row_id"
          class="hint"
          >订单 {{ order.order_id }} / {{ order.line_id }} · {{ order.sku }} ·
          {{ order.status }} · {{ order.fulfillment_status }}</text
        ><view class="row"
          ><text>已逐行核验订单关联</text
          ><switch
            :checked="orderVerified"
            :disabled="busy"
            @change="orderVerified = checked($event)" /></view
        ><view v-for="policy in support.policies" :key="policy.id"
          ><text class="label"
            >{{ policy.data?.title }} · {{ policy.availability }}</text
          ><text class="prose">{{ policy.data?.text }}</text
          ><switch
            :checked="policyIds.includes(policy.id)"
            :disabled="busy || policy.availability !== 'effective'"
            @change="togglePolicy(policy.id, checked($event))" /></view
      ></view>
      <view v-if="form.template === 'daily_model'"
        ><button :disabled="busy" @tap="operationPreview">
          读取运营数据发送范围</button
        ><view v-if="operation"
          ><text
            v-for="branch in operation.preview.branches"
            :key="branch.name"
            class="hint"
            >{{ branch.name }} · {{ branch.count }} · {{ branch.reason }}</text
          ><text
            v-for="finding in operation.preview.findings"
            :key="finding.object_label"
            >{{ finding.title }} · {{ finding.basis }} ·
            {{ finding.advice }}</text
          ><text class="hint">预览哈希 {{ operation.preview_hash }}</text
          ><SourceList
            :sources="operation.preview.sources"
            :shop-id="account.shopId" /></view
      ></view>
      <text class="label">步数 / 秒数 / 模型美元预算</text
      ><input
        v-model.number="form.budget.max_steps"
        type="number"
        :disabled="busy"
      /><input
        v-model.number="form.budget.max_seconds"
        type="number"
        :disabled="busy"
      /><input
        v-model="form.budget.max_cost_usd"
        type="digit"
        :disabled="busy"
      />
      <text v-if="model" class="hint"
        >{{ agentLabels[model.status] || model.status }} ·
        {{ model.provider }} / {{ model.model }} ·
        {{ model.reason }}；输入/输出每百万token
        {{ model.input_usd_per_million ?? '未知' }} /
        {{ model.output_usd_per_million ?? '未知' }} USD。{{
          model.cost_note
        }}</text
      >
      <view class="row"
        ><text>同意目标发送至所示模型</text
        ><switch
          :checked="form.allow_model"
          :disabled="busy"
          @change="form.allow_model = checked($event)"
      /></view>
      <view class="row"
        ><text>同意发送匿名聚合分析事实</text
        ><switch
          :checked="form.allow_analysis_data"
          :disabled="busy"
          @change="form.allow_analysis_data = checked($event)"
      /></view>
      <view class="row"
        ><text>同意发送所选商品名称和参数</text
        ><switch
          :checked="form.allow_listing_data"
          :disabled="busy"
          @change="form.allow_listing_data = checked($event)"
      /></view>
      <view class="row"
        ><text>同意发送已审消息、订单及政策</text
        ><switch
          :checked="form.allow_support_data"
          :disabled="busy"
          @change="form.allow_support_data = checked($event)"
      /></view>
      <view class="row"
        ><text>同意发送运营聚合检查数据</text
        ><switch
          :checked="form.allow_operation_data"
          :disabled="busy || !operation"
          @change="form.allow_operation_data = checked($event)"
      /></view>
      <button
        class="primary"
        :loading="busy"
        :disabled="busy || rulesPending || !!pending"
        @tap="submit(false)"
      >
        启动任务
      </button>
    </view>
    <view class="card"
      ><view class="row"
        ><text class="section-title">执行历史</text
        ><button :disabled="busy" @tap="refresh">刷新回读</button></view
      ><text v-if="!runs.length" class="muted">尚无运行记录。</text
      ><button
        v-for="item in runs"
        :key="item.id"
        :disabled="busy"
        @tap="inspect(item.id)"
      >
        #{{ item.id }} · {{ agentLabels[item.template] || item.template }} ·
        {{ agentLabels[item.status] || item.status }}
      </button></view
    >
    <view v-if="run" class="card">
      <text class="section-title">任务 #{{ run.id }} · v{{ run.version }}</text
      ><text
        >{{ agentLabels[run.status] || run.status }} · {{ run.source_status }} ·
        {{ agentLabels[run.next_node] || run.next_node }}</text
      ><text class="hint">{{ agentReasons[run.reason] || run.reason }}</text
      ><text class="hint"
        >{{ run.created_at }} · 来源版本 {{ run.source_revision }} ·
        外部未提交</text
      >
      <text v-if="run.input" class="hint"
        >保存范围 {{ run.input.scope.start_at }} 至
        {{ run.input.scope.end_at }} · {{ run.input.scope.timezone }} ·
        {{ run.input.scope.currency }} · {{ run.input.scope.data_identity }} /
        {{ run.input.scope.channel }}</text
      >
      <text
        >步数 {{ run.steps_used }}/{{ run.budget.max_steps }} ·
        {{ run.elapsed_ms / 1000 }}/{{ run.budget.max_seconds }} 秒</text
      ><text class="hint"
        >已用 {{ run.spent_usd }} / {{ run.budget.max_cost_usd }} USD ·
        未确认预留 {{ run.reserved_usd }} USD</text
      >
      <AgentEvidence :run="run" />
      <button v-if="run.input" :disabled="busy || !!pending" @tap="reuseInput">
        按原范围准备新任务
      </button>
      <view v-if="run.status === 'waiting_approval'"
        ><text class="label"
          >R1 当前节点审批：{{
            agentLabels[run.next_node] || run.next_node
          }}</text
        ><text class="hint">{{
          run.next_node === 'analysis_todo'
            ? '保存分析快照与核对待办。下一节点需单独审批。'
            : run.next_node === 'listing_draft'
              ? '根据商品事实保存本地模板草稿，之后在 Listing 页单独审批生效。拒绝本节点保留此前分析结果。'
              : '将已审阅候选保存为内部记录，业务处理仍需在对应页面核对。'
        }}</text
        ><view class="row"
          ><text>已审阅当前版本全部依据</text
          ><switch
            :checked="reviewed"
            :disabled="busy"
            @change="reviewed = checked($event)" /></view
      ></view>
      <view v-if="actions.includes('resume')"
        ><text class="label">恢复后总预算：步数 / 秒数 / USD</text
        ><input
          v-model.number="resumeBudget.max_steps"
          type="number"
          :disabled="busy"
        /><input
          v-model.number="resumeBudget.max_seconds"
          type="number"
          :disabled="busy"
        /><input
          v-model="resumeBudget.max_cost_usd"
          type="digit"
          :disabled="busy"
        /><text class="hint"
          >总预算不能低于原值；模型结果被丢弃后恢复可能重新计费。</text
        ></view
      >
      <text v-if="unknownAction" class="error"
        >上次操作结果待核对，先刷新回读后再操作。</text
      ><button
        v-for="action in actions"
        :key="action"
        :disabled="busy || unknownAction || (action === 'approve' && !reviewed)"
        @tap="act(action)"
      >
        {{ labels[action] }}
      </button>
      <AgentResult
        v-for="record in records"
        :key="`${record.kind}-${record.id}`"
        :kind="record.kind"
        :id="record.id"
        :shop="run.shop_id"
        :path="record.path"
        :record-key="record.key"
      />
      <text class="label">步骤与操作历史</text
      ><view v-for="step in run.steps" :key="step.id" class="card"
        ><text
          >{{ agentLabels[step.node] || step.node }} ·
          {{ agentLabels[step.status] || step.status }}</text
        ><text class="hint"
          >{{ step.skill }} v{{ step.skill_version }} · {{ step.duration_ms }}ms
          · {{ step.created_at }}</text
        ><text>{{ agentReasons[step.reason] || step.reason }}</text
        ><text class="hint">下一节点 {{ step.next_node }}</text></view
      >
    </view>
    <InternalAuthorizations
      :run="run"
      :busy="busy"
      @use="act('use_authorization', $event)"
      @start="startAuthorized"
      @inspect="inspect"
    />
    <view class="card"
      ><text class="section-title">技能与权限 · {{ skills.length }}</text
      ><view v-for="skill in skills" :key="skill.name" class="card"
        ><text class="label">{{ skill.purpose }} · {{ skill.risk }}</text
        ><text class="hint"
          >{{ skill.name }} v{{ skill.version }} · {{ skill.read_scope }} /
          {{ skill.write_scope }}</text
        ><text>{{ skill.preconditions.join('；') }}</text
        ><text class="hint"
          >{{ skill.permissions.join('；') }} · {{ skill.confirmation }} ·
          {{ skill.failure_policy }}</text
        ></view
      ></view
    >
  </view>
</template>
<style scoped>
.prose {
  display: block;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
