// route: /statements
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import { ApiError } from '../../services/client'
import { queryString, requestId } from '../../services/task-policy'
import { openLink as openRoute } from '../../services/navigation'
import { supportTime } from '../../services/support-types'
import SourceList from '../../components/SourceList.vue'
import {
  availableActions,
  blockedOutcomes,
  canEdit,
  checkedOrderScope,
  checkedReviewDraft,
  checkedScope,
  channels,
  comparisonStatuses,
  controlBody,
  controls,
  emptyConclusion,
  emptyOrderScope,
  emptyStatementScope,
  entryTypes,
  identities,
  isCurrentVersion,
  mappingStatuses,
  reviewOutcomeKeys,
  reviewOutcomes,
  reviewStatuses,
  reviewsPerPage,
  statementLineLabel,
  statementLinesPerPage,
  trimmedAmount,
  type ControlAction,
  type FeeComparison,
  type OrderReconciliation,
  type OrderReconciliationScope,
  type ReviewConclusion,
  type ReviewControlBody,
  type ReviewCurrent,
  type ReviewDraftBody,
  type ReviewOutcome,
  type ReviewPage,
  type ReviewPreview,
  type ReviewSaved,
  type ReviewWriteBody,
  type StatementItem,
  type StatementReconciliation,
  type StatementScope,
} from '../../services/statement-policy'

const scope = reactive<StatementScope>(emptyStatementScope())
const result = ref<StatementReconciliation>()
const orderResult = ref<OrderReconciliation>()
const reviews = ref<ReviewSaved[]>([])
const cursor = ref<number | null>(null)
const saved = ref<ReviewSaved>()
const shownVersion = ref<number | null>(null)
const conclusion = reactive<ReviewConclusion>(emptyConclusion())
const editing = reactive({
  id: 0,
  version: 0,
  scope: emptyStatementScope(),
  open: false,
})
const preview = ref<ReviewPreview>()
const readBack = ref<ReviewPreview>()
const confirmed = ref(false)
const controlOpen = ref(false)
const controlConfirmed = ref(false)
const controlAction = ref<ControlAction>('withdraw')
const linePage = ref(0)
const orderLinePage = ref(0)
const orderScope = reactive<OrderReconciliationScope>(emptyOrderScope())
const busy = ref(false)
const error = ref('')
const notice = ref('')
const pending = ref<ReviewWriteBody>()
const pendingControl = ref<{
  review_id: number
  action: ControlAction
  body: ReviewControlBody
} | null>(null)
let alive = true
let epoch = 0
let linked: Record<string, string> = {}
const request = scopedRequest(api, () => (alive ? epoch : null))
const timezone = computed(
  () =>
    account.shops.find((s) => s.id === account.shopId)?.timezone ||
    'Asia/Shanghai',
)
const actions = computed(() => availableActions(saved.value?.status || ''))
const comparisonSummary = computed(() =>
  result.value
    ? statusSummary(result.value.comparisons.map((item) => item.status))
    : '',
)
const orderSummary = computed(() =>
  orderResult.value
    ? statusSummary(orderResult.value.comparisons.map((item) => item.status))
    : '',
)
const visibleLines = computed(() =>
  (result.value?.statements || []).slice(
    linePage.value * statementLinesPerPage,
    linePage.value * statementLinesPerPage + statementLinesPerPage,
  ),
)
const visibleOrderLines = computed(() =>
  (orderResult.value?.orders || []).slice(
    orderLinePage.value * statementLinesPerPage,
    orderLinePage.value * statementLinesPerPage + statementLinesPerPage,
  ),
)
const blocked = computed(() =>
  blockedOutcomes(preview.value?.snapshot.blockers || []),
)
const hiddenOutcomes = computed(() =>
  blocked.value.length
    ? reviewOutcomeKeys.filter((item) => !blocked.value.includes(item))
    : reviewOutcomeKeys,
)

useLoad((params) => {
  linked = params as Record<string, string>
})
useUnload(() => {
  alive = false
  epoch++
})
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    epoch++
    reset()
    error.value = '请返回工作台登录并选择店铺。'
  },
  { flush: 'sync' },
)
watch(scope, () => {
  result.value = undefined
  orderResult.value = undefined
  reviews.value = []
  cursor.value = null
  saved.value = undefined
  shownVersion.value = null
  readBack.value = undefined
  controlOpen.value = false
  linePage.value = 0
  orderLinePage.value = 0
  error.value = ''
  notice.value = ''
})

function statusSummary(values: string[]) {
  const counts = new Map<string, number>()
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1)
  return [...counts.entries()]
    .map(([key, count]) => `${key} ${count}`)
    .sort()
    .join(' · ')
}

function comparisonLabel(item: FeeComparison) {
  return comparisonStatuses[item.status] || item.status
}

function mappingLabel(status: string) {
  return mappingStatuses[status as keyof typeof mappingStatuses] || status
}

function outcomeLabel(outcome: string) {
  return reviewOutcomes[outcome as ReviewOutcome] || outcome
}

function historyLabel(version: number, action: string, created: string) {
  return `v${version} · ${action} · ${supportTime(created, scope.timezone)}`
}

function reset() {
  result.value = undefined
  orderResult.value = undefined
  reviews.value = []
  cursor.value = null
  saved.value = undefined
  shownVersion.value = null
  readBack.value = undefined
  preview.value = undefined
  confirmed.value = false
  controlOpen.value = false
  controlConfirmed.value = false
  editing.open = false
  editing.id = 0
  editing.version = 0
  Object.assign(conclusion, emptyConclusion())
  linePage.value = 0
  orderLinePage.value = 0
  error.value = ''
  notice.value = ''
}

async function perform(work: () => Promise<void>) {
  if (busy.value || !alive) return
  const token = epoch
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await work()
  } catch (cause) {
    if (alive && token === epoch)
      error.value =
        cause instanceof Error
          ? cause.message
          : '账单核对未完成，请回读记录核对。'
  } finally {
    if (alive) busy.value = false
  }
}

function requireShop() {
  if (!account.session || !account.shopId)
    throw new Error('请先登录并选择店铺。')
  return account.shopId
}

async function reconcile() {
  const shop = requireShop()
  await perform(async () => {
    result.value = await request<StatementReconciliation>(
      `/shops/${shop}/statements/reconcile`,
      'POST',
      checkedScope(scope),
    )
    orderResult.value = undefined
    linePage.value = 0
    notice.value = '已读取当前账单与人工费用；来源变化后请重新读取。'
  })
}

async function reconcileOrders() {
  const shop = requireShop()
  await perform(async () => {
    orderResult.value = await request<OrderReconciliation>(
      `/shops/${shop}/statements/orders/reconcile`,
      'POST',
      checkedOrderScope(orderScope),
    )
    orderLinePage.value = 0
    notice.value =
      '订单与账单匹配结果已读取；本清单为只读结果，不保存人工结论。'
  })
}

async function listReviews(more = false) {
  const shop = requireShop()
  const input = checkedScope(scope)
  const query = queryString({
    data_identity: input.data_identity,
    channel: input.channel,
    before: more && cursor.value ? cursor.value : '',
  })
  const page = await request<ReviewPage>(
    `/shops/${shop}/statement-reviews?${query}`,
  )
  reviews.value = more ? [...reviews.value, ...page.items] : page.items
  cursor.value = page.next_cursor
}

async function show(id: number, version?: number) {
  const shop = requireShop()
  const target = version
    ? `/shops/${shop}/statement-reviews/${id}?version=${version}`
    : `/shops/${shop}/statement-reviews/${id}`
  const value = await request<ReviewSaved>(target)
  saved.value = value
  shownVersion.value = version ?? value.content_version
  readBack.value = undefined
  controlOpen.value = false
  controlConfirmed.value = false
  controlAction.value = value.status === 'withdrawn' ? 'clear' : 'withdraw'
}

function begin(record?: ReviewSaved) {
  const snapshot = record?.snapshot
  preview.value = undefined
  confirmed.value = false
  readBack.value = undefined
  editing.open = true
  editing.id = record?.id || 0
  editing.version = record?.version || 0
  editing.scope = { ...(snapshot?.result.scope || scope) }
  Object.assign(
    conclusion,
    snapshot?.conclusion ? { ...snapshot.conclusion } : emptyConclusion(),
  )
}

function draft(): ReviewDraftBody {
  return checkedReviewDraft({
    scope: { ...editing.scope },
    review_id: editing.id || null,
    version: editing.version,
    conclusion: { ...conclusion },
  })
}

async function inspect() {
  const shop = requireShop()
  await perform(async () => {
    preview.value = undefined
    confirmed.value = false
    preview.value = await request<ReviewPreview>(
      `/shops/${shop}/statement-reviews/preview`,
      'POST',
      draft(),
    )
    notice.value = '预览已重新计算账单、费用与规则依据，保存前请核对待核事项。'
  })
}

async function save(retry = false) {
  const shop = requireShop()
  if (!retry) {
    if (!preview.value || !confirmed.value) return
    pending.value = {
      ...draft(),
      preview_hash: preview.value.preview_hash,
      request_id: requestId(),
      confirm: true,
    }
  }
  const body = pending.value
  if (!body) return
  await perform(async () => {
    let value: ReviewSaved
    try {
      value = await request<ReviewSaved>(
        `/shops/${shop}/statement-reviews`,
        'POST',
        body,
      )
    } catch (cause) {
      // 只有确定性 4xx 才允许修正后新建 request_id；结果未知保留同次恢复入口。
      if (
        cause instanceof ApiError &&
        cause.status >= 400 &&
        cause.status < 500
      )
        pending.value = undefined
      throw cause
    }
    saved.value = await request<ReviewSaved>(
      `/shops/${shop}/statement-reviews/${value.id}`,
    )
    shownVersion.value = saved.value.content_version
    pending.value = undefined
    preview.value = undefined
    confirmed.value = false
    editing.open = false
    await listReviews()
    notice.value = '已按记录编号独立回读核对存档与版本。'
  })
}

async function readCurrent() {
  const shop = requireShop()
  const id = saved.value?.id
  if (!id) return
  await perform(async () => {
    const value = await request<ReviewCurrent>(
      `/shops/${shop}/statement-reviews/${id}/current`,
    )
    saved.value = value.record
    shownVersion.value = value.record.content_version
    readBack.value = value.preview || undefined
    controlOpen.value = false
    notice.value = value.preview
      ? '当前来源、费用与规则已重新计算；本次读取不会更新历史结论。'
      : '该存档没有可回读的正文依据。'
  })
}

async function control(retry = false) {
  const shop = requireShop()
  if (!retry) {
    if (!saved.value || !controlConfirmed.value) return
    pendingControl.value = {
      review_id: saved.value.id,
      action: controlAction.value,
      body: controlBody(saved.value.version, requestId()),
    }
  }
  const target = pendingControl.value
  if (!target) return
  const id = target.review_id
  const action = target.action
  if (!retry) {
    const answer = await Taro.showModal({
      title: action === 'clear' ? '清除核对存档' : '撤销核对结论',
      content:
        action === 'clear'
          ? '清除将擦除这份存档所有版本的说明与依据，无法恢复；原账单、费用与规则各自保留。确认继续？'
          : '撤销后可查看历史，当前结论不再生效。确认继续？',
    })
    if (!answer.confirm || saved.value?.id !== id || !account.session) return
  }
  await perform(async () => {
    let value: ReviewSaved
    try {
      value = await request<ReviewSaved>(
        `/shops/${shop}/statement-reviews/${id}/${action}`,
        'POST',
        target.body,
      )
    } catch (cause) {
      if (
        cause instanceof ApiError &&
        cause.status >= 400 &&
        cause.status < 500
      )
        pendingControl.value = null
      throw cause
    }
    saved.value = await request<ReviewSaved>(
      `/shops/${shop}/statement-reviews/${id}`,
    )
    shownVersion.value = saved.value.content_version
    readBack.value = undefined
    pendingControl.value = null
    controlConfirmed.value = false
    controlOpen.value = false
    controlAction.value =
      saved.value.status === 'withdrawn' ? 'clear' : 'withdraw'
    if (saved.value.status === 'cleared') {
      Object.assign(conclusion, emptyConclusion())
      preview.value = undefined
      pending.value = undefined
      editing.open = false
    }
    await listReviews()
    notice.value =
      value.status === 'cleared'
        ? '正文与历史依据已清除，仅保留范围、状态与审计。'
        : '结论已撤销并保留历史。'
  })
}

function pickIdentity(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  scope.data_identity = identities[index] || 'user_import'
}

function pickChannel(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  scope.channel = channels[index] || 'generic'
}

function pickOutcome(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  conclusion.outcome = reviewOutcomeKeys[index] || 'pending'
  confirmed.value = false
}

function pickSaleBasis(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  orderScope.sale_basis = index === 1 ? 'merchandise_after_discount' : 'unknown'
  if (orderScope.sale_basis === 'unknown') orderScope.basis_note = ''
  orderResult.value = undefined
}

function pickControlAction(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  controlAction.value = actions.value[index] || 'withdraw'
  controlConfirmed.value = false
}

function toggleConfirmed(event: unknown) {
  confirmed.value = Boolean(
    (event as { detail: { value: boolean } }).detail.value,
  )
}

function toggleControl(event: unknown) {
  controlConfirmed.value = Boolean(
    (event as { detail: { value: boolean } }).detail.value,
  )
}

function editConclusion() {
  confirmed.value = false
}

function openPage(path: string, query: Record<string, string> = {}) {
  void openRoute(path, { shop: String(account.shopId || ''), ...query }).catch(
    (cause: unknown) => {
      error.value =
        cause instanceof Error ? cause.message : '打开业务页面失败。'
    },
  )
}

function moreLines() {
  if (!result.value) return
  if (
    (linePage.value + 1) * statementLinesPerPage <
    result.value.statements.length
  )
    linePage.value++
}

function fewerLines() {
  linePage.value = Math.max(0, linePage.value - 1)
}

function moreOrderLines() {
  if (!orderResult.value) return
  if (
    (orderLinePage.value + 1) * statementLinesPerPage <
    orderResult.value.orders.length
  )
    orderLinePage.value++
}

function fewerOrderLines() {
  orderLinePage.value = Math.max(0, orderLinePage.value - 1)
}

useDidShow(() => {
  void perform(async () => {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    if (linked.shop && Number(linked.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不同，请切换店铺后重试。')
    Object.assign(scope, emptyStatementScope(timezone.value))
    Object.assign(orderScope, emptyOrderScope(timezone.value))
    Object.assign(conclusion, emptyConclusion())
    const id = Number(linked.review || 0)
    linked = {}
    await listReviews()
    if (Number.isSafeInteger(id) && id > 0) await show(id)
  })
})
</script>

<template>
  <view class="screen">
    <view class="hero">
      <text class="eyebrow">SOLOOPS · STATEMENTS</text>
      <text class="title">账单与费用，逐行核对。</text>
      <text class="muted">从原始账单到人工凭据，保留每一处差异的依据。</text>
    </view>
    <view class="card">
      <text class="hint"
        >销售款、退款、费用与平台记载回款分别合计。文件覆盖与费用完整性未知，待重核/撤销费用不参与比较，无法确定净利润或银行到账。</text
      >
      <button :disabled="busy" @tap="openPage('/settlements')">
        登记结算周期与人工回款
      </button>
      <button
        :disabled="busy"
        @tap="
          openPage('/order-reconciliation', {
            data_identity: scope.data_identity,
            channel: scope.channel,
          })
        "
      >
        订单账单核对（独立页面）
      </button>
      <button
        :disabled="busy"
        @tap="openPage('/imports', { kind: 'statements' })"
      >
        导入或查看账单批次
      </button>
    </view>
    <text v-if="error" class="error">{{ error }}</text>
    <text v-if="notice" class="hint">{{ notice }}</text>
    <view class="card">
      <text class="section-title">核对范围</text>
      <picker
        :range="['用户导入', '合成测试']"
        :value="identities.indexOf(scope.data_identity)"
        :disabled="busy"
        @change="pickIdentity"
        ><view class="select"
          >身份：{{
            scope.data_identity === 'synthetic' ? '合成测试' : '用户导入'
          }}</view
        ></picker
      >
      <picker
        :range="channels"
        :value="channels.indexOf(scope.channel)"
        :disabled="busy"
        @change="pickChannel"
        ><view class="select">渠道：{{ scope.channel }}</view></picker
      >
      <text class="label">开始时间（含偏移，含开始）</text>
      <input
        v-model="scope.start_at"
        :disabled="busy"
        placeholder="2026-09-12T00:00:00+08:00"
      />
      <text class="label">结束时间（含偏移，不含结束）</text>
      <input
        v-model="scope.end_at"
        :disabled="busy"
        placeholder="2026-10-12T00:00:00+08:00"
      />
      <text class="label">核对显示时区（IANA）</text>
      <input
        v-model="scope.timezone"
        :disabled="busy"
        placeholder="Asia/Shanghai"
      />
      <text class="hint"
        >包含开始、不含结束，最多 366 天、1000 行账单及 1000
        笔费用；两侧按各自发生时间筛选。</text
      >
      <button class="primary" :disabled="busy" :loading="busy" @tap="reconcile">
        读取并核对账单与费用
      </button>
    </view>
    <view v-if="result" class="card">
      <text class="section-title"
        >核对结果 · 来源版本 {{ result.source_revision }} · 规则变更号
        {{ result.rule_revision }}</text
      >
      <text class="hint"
        >计算于
        {{ supportTime(result.calculated_at, result.scope.timezone) }}；范围
        {{ supportTime(result.scope.start_at, result.scope.timezone) }} 至
        {{
          supportTime(result.scope.end_at, result.scope.timezone)
        }}（结束不含，{{ result.scope.timezone }}）</text
      >
      <text
        v-for="total in result.totals"
        :key="`${total.currency}-${total.entry_type}`"
        >{{ total.currency }} ·
        {{ entryTypes[total.entry_type] || total.entry_type }}：
        {{ trimmedAmount(total.amount) }} （{{ total.count }} 笔）</text
      >
      <text v-if="comparisonSummary" class="hint"
        >比对状态：{{ comparisonSummary }}</text
      >
      <text
        v-if="result.stale_expenses || result.withdrawn_expenses"
        class="error"
        >待重核费用 {{ result.stale_expenses }} 笔 · 已撤销
        {{ result.withdrawn_expenses }} 笔未参与比较。</text
      >
      <text class="section-title"
        >费用比对（{{ result.comparisons.length }}）</text
      >
      <text v-if="!result.comparisons.length" class="muted"
        >当前范围内没有可核对的费用。请检查账单导入或人工费用范围。</text
      >
      <view
        v-for="(item, index) in result.comparisons"
        :key="`${item.evidence_ref}-${index}`"
        class="record"
      >
        <text>{{ item.evidence_ref }} · {{ comparisonLabel(item) }}</text>
        <text class="hint"
          >账单行 {{ item.statement_ids.join('、') || '无' }} · 人工费用
          {{
            item.expenses.map((expense) => `#${expense.id}`).join('、') || '无'
          }}
          · 差额 {{ trimmedAmount(item.difference) }}</text
        >
        <text v-for="expense in item.expenses" :key="expense.id" class="hint"
          >人工费用 #{{ expense.id }} v{{ expense.version }} ·
          {{ expense.label }} · {{ expense.category }} /
          {{ expense.allocation }} · {{ expense.currency }}
          {{ trimmedAmount(expense.amount) }} · 发生
          {{ supportTime(expense.occurred_at, scope.timezone) }}</text
        >
      </view>
      <text class="section-title"
        >收费分类规则（{{ result.mappings.length }}）</text
      >
      <view
        v-for="item in result.mappings"
        :key="item.statement_id"
        class="record"
      >
        <text
          >账单行 #{{ item.statement_id }} ·
          {{ mappingLabel(item.status) }}</text
        >
        <text class="hint"
          >类别 {{ item.category || '未知' }} · 规则
          {{
            item.rule_id ? `#${item.rule_id} v${item.rule_version}` : '未匹配'
          }}</text
        >
      </view>
      <text class="section-title">核对口径</text>
      <text v-for="check in result.checks" :key="check" class="hint">{{
        check
      }}</text>
    </view>
    <view v-if="result" class="card">
      <text class="section-title"
        >账单明细（{{ result.statements.length }}）</text
      >
      <text v-if="!result.statements.length" class="muted"
        >当前范围没有账单行；请调整范围或先导入渠道账单。</text
      >
      <view v-for="(line, index) in visibleLines" :key="line.id" class="record">
        <text>{{
          statementLineLabel(line, linePage * statementLinesPerPage + index)
        }}</text>
        <text class="hint"
          >{{ line.currency }} {{ trimmedAmount(line.amount) }} · 发生
          {{ supportTime(line.occurred_at, result.scope.timezone) }}</text
        >
        <SourceList :sources="[line.source]" :shop-id="account.shopId" />
      </view>
      <view class="row">
        <button :disabled="busy || linePage === 0" @tap="fewerLines">
          上一页
        </button>
        <text
          >{{ linePage + 1 }} /
          {{
            Math.max(
              1,
              Math.ceil(result.statements.length / statementLinesPerPage),
            )
          }}</text
        >
        <button
          :disabled="
            busy ||
            (linePage + 1) * statementLinesPerPage >= result.statements.length
          "
          @tap="moreLines"
        >
          下一页
        </button>
      </view>
    </view>
    <view class="card">
      <text class="section-title">订单账单核对（H14 · 共用结果语义）</text>
      <text class="hint"
        >按订单号精确关联窗口外来源行；窗口选取候选，同订单号全部当前行作为依据。</text
      >
      <text class="label">销售金额口径</text>
      <picker
        :range="[
          '尚未核实金额组成，仅查看待核依据',
          '已核实两侧均为退款前折后商品款',
        ]"
        :value="orderScope.sale_basis === 'unknown' ? 0 : 1"
        :disabled="busy"
        @change="pickSaleBasis"
        ><view class="select">{{ orderScope.sale_basis }}</view></picker
      >
      <text v-if="orderScope.sale_basis !== 'unknown'" class="label"
        >两侧金额组成依据（原文件与列名，不含客户信息）</text
      >
      <textarea
        v-if="orderScope.sale_basis !== 'unknown'"
        v-model="orderScope.basis_note"
        :maxlength="500"
        :disabled="busy"
      />
      <text class="label">订单核对起止（含偏移，结束不含）</text>
      <input v-model="orderScope.start_at" :disabled="busy" />
      <input v-model="orderScope.end_at" :disabled="busy" />
      <text class="label">订单核对显示时区（IANA）</text>
      <input v-model="orderScope.timezone" :disabled="busy" />
      <button class="primary" :disabled="busy" @tap="reconcileOrders">
        读取订单与账单匹配
      </button>
      <button
        :disabled="busy"
        @tap="
          openPage('/order-reconciliation', {
            data_identity: orderScope.data_identity,
            channel: orderScope.channel,
          })
        "
      >
        在独立页面核对（/order-reconciliation）
      </button>
    </view>
    <view v-if="orderResult" class="card">
      <text class="section-title"
        >订单核对结果 · 来源版本 {{ orderResult.source_revision }}</text
      >
      <text class="hint"
        >计算于
        {{ supportTime(orderResult.calculated_at, orderResult.scope.timezone) }}
        · 覆盖状态 {{ orderResult.coverage }} · 口径
        {{ orderResult.scope.sale_basis }}</text
      >
      <text v-if="orderSummary" class="hint">比对状态：{{ orderSummary }}</text>
      <text class="section-title"
        >比对（{{ orderResult.comparisons.length }}）</text
      >
      <text v-if="!orderResult.comparisons.length" class="muted"
        >当前窗口没有可比订单或账单销售/退款行。</text
      >
      <view
        v-for="(item, index) in orderResult.comparisons"
        :key="`${item.order_id}-${item.entry_type}-${index}`"
        class="record"
      >
        <text
          >订单 {{ item.order_id }} ·
          {{ entryTypes[item.entry_type] || item.entry_type }} ·
          {{ item.status }}</text
        >
        <text class="hint"
          >账单行 {{ item.statement_ids.join('、') || '无' }} · 订单行
          {{ item.order_line_ids.join('、') || '无' }} · 币种
          {{ item.currency || '未知' }} · 可比订单金额
          {{ trimmedAmount(item.order_amount) }} · 差额
          {{ trimmedAmount(item.difference) }}</text
        >
        <text v-for="reason in item.reasons" :key="reason" class="hint">{{
          reason
        }}</text>
      </view>
      <text class="section-title"
        >窗口订单行（{{ orderResult.orders.length }}）</text
      >
      <view
        v-for="(line, index) in visibleOrderLines"
        :key="line.id"
        class="record"
      >
        <text
          >{{ orderLinePage * statementLinesPerPage + index + 1 }}. 订单
          {{ line.order_id }} / 行 {{ line.line_id }} · {{ line.sku }} ·
          {{ line.status }} · {{ line.fulfillment_status }}</text
        >
        <text class="hint"
          >{{ line.currency }} 单价 {{ trimmedAmount(line.unit_price) }} ×
          {{ line.quantity }} · 折扣 {{ trimmedAmount(line.discount) }} · 退款
          {{ trimmedAmount(line.refund) }} · 下单
          {{ supportTime(line.ordered_at, orderResult.scope.timezone) }} ·
          {{ line.in_window ? '窗口内' : '窗口外关联' }}</text
        >
        <SourceList :sources="[line.source]" :shop-id="account.shopId" />
      </view>
      <view class="row">
        <button :disabled="busy || orderLinePage === 0" @tap="fewerOrderLines">
          上一页
        </button>
        <text
          >{{ orderLinePage + 1 }} /
          {{
            Math.max(
              1,
              Math.ceil(orderResult.orders.length / statementLinesPerPage),
            )
          }}</text
        >
        <button
          :disabled="
            busy ||
            (orderLinePage + 1) * statementLinesPerPage >=
              orderResult.orders.length
          "
          @tap="moreOrderLines"
        >
          下一页
        </button>
      </view>
      <text class="section-title"
        >账单销售/退款行（{{ orderResult.statements.length }}）</text
      >
      <text
        v-for="line in orderResult.statements.slice(0, statementLinesPerPage)"
        :key="line.id"
        class="hint"
        >{{ statementLineLabel(line, 0) }} · {{ line.currency }}
        {{ trimmedAmount(line.amount) }}</text
      >
      <text class="section-title">核对口径</text>
      <text v-for="check in orderResult.checks" :key="check" class="hint">{{
        check
      }}</text>
    </view>
    <view class="card">
      <text class="section-title"
        >人工核对存档（{{ reviews.length }} / 每页 {{ reviewsPerPage }}）</text
      >
      <text v-if="!reviews.length" class="muted"
        >没有符合当前范围的核对存档。人工结论须先预览再确认保存。</text
      >
      <button
        v-for="item in reviews"
        :key="item.id"
        :disabled="busy"
        @tap="perform(() => show(item.id))"
      >
        核对 #{{ item.id }} · {{ reviewStatuses[item.status] || '状态未知' }} ·
        v{{ item.version }} · {{ supportTime(item.created_at, scope.timezone) }}
      </button>
      <button :disabled="busy" @tap="perform(() => listReviews())">
        读取核对存档
      </button>
      <button
        :disabled="busy || !cursor"
        @tap="perform(() => listReviews(true))"
      >
        加载更早存档
      </button>
      <button class="primary" :disabled="busy" @tap="begin()">
        新建核对结论
      </button>
      <button v-if="pending" class="danger" :disabled="busy" @tap="save(true)">
        回查原结论保存请求（不更换 request_id）
      </button>
      <button
        v-if="pendingControl"
        class="danger"
        :disabled="busy"
        @tap="control(true)"
      >
        回查原处理请求（不更换 request_id）
      </button>
      <text v-if="pending" class="hint"
        >上次保存结果未知，已冻结请求标识；再次提交只会返回同一结果。</text
      >
      <text v-if="pendingControl" class="hint"
        >上次撤销/清除结果未知，已冻结请求标识与版本；再次提交只会返回同一结果。</text
      >
    </view>
    <view v-if="editing.open" class="card">
      <text class="section-title">{{
        editing.id ? `修订核对 #${editing.id}` : '新建人工核对'
      }}</text>
      <text class="hint"
        >本次存档范围
        {{ supportTime(editing.scope.start_at, editing.scope.timezone) }} 至
        {{
          supportTime(editing.scope.end_at, editing.scope.timezone)
        }}（结束不含，{{ editing.scope.timezone }}）</text
      >
      <text class="label">存档范围开始（含偏移）</text>
      <input v-model="editing.scope.start_at" :disabled="busy" />
      <text class="label">存档范围结束（含偏移）</text>
      <input v-model="editing.scope.end_at" :disabled="busy" />
      <text class="label">存档时区（IANA）</text>
      <input v-model="editing.scope.timezone" :disabled="busy" />
      <text class="label">人工结论</text>
      <picker
        :range="hiddenOutcomes.map((item) => reviewOutcomes[item])"
        :value="Math.max(0, hiddenOutcomes.indexOf(conclusion.outcome))"
        :disabled="busy"
        @change="pickOutcome"
        ><view class="select">{{
          outcomeLabel(conclusion.outcome)
        }}</view></picker
      >
      <text v-if="blocked.length" class="error"
        >仍有待核事项时只能保存待核结论：{{ blocked.join('；') }}</text
      >
      <text class="label">核对依据与差异说明（1–1000 字）</text>
      <textarea
        v-model="conclusion.note"
        :maxlength="1000"
        :disabled="busy"
        placeholder="说明本次范围、依据与差异原因，不写客户个人信息"
        @input="editConclusion"
      />
      <text class="hint"
        >金额差异已说明表示已记录人工解释，仍需跟进处理；一致仅表示编号、币种与金额一致。</text
      >
      <button class="primary" :disabled="busy" @tap="inspect">
        预览结论与依据
      </button>
      <button
        :disabled="busy"
        @tap="begin(saved && saved.id === editing.id ? saved : undefined)"
      >
        放弃编辑并重新开始
      </button>
    </view>
    <view v-if="preview" class="card">
      <text class="section-title">预览 · 尚未保存</text>
      <text
        >{{ outcomeLabel(preview.snapshot.conclusion.outcome) }} ·
        {{ preview.snapshot.conclusion.note }}</text
      >
      <text class="hint"
        >预览哈希 {{ preview.preview_hash.slice(0, 12) }}… · 账单来源版本
        {{ preview.snapshot.result.source_revision }} · 费用变更号
        {{ preview.snapshot.expense_revision }} · 规则变更号
        {{ preview.snapshot.result.rule_revision }}</text
      >
      <text
        v-for="item in preview.snapshot.blockers"
        :key="item"
        class="error"
        >{{ item }}</text
      >
      <checkbox-group @change="toggleConfirmed">
        <label class="label"
          ><checkbox
            value="confirm"
            :checked="confirmed"
            :disabled="busy"
          />我已核对本窗口的来源、费用、规则和差异说明，确认保存人工结论</label
        >
      </checkbox-group>
      <button class="primary" :disabled="busy || !confirmed" @tap="save()">
        保存核对结论
      </button>
    </view>
    <view v-if="saved" class="card">
      <view class="row">
        <text class="section-title">核对 #{{ saved.id }}</text>
        <text class="badge">{{
          reviewStatuses[saved.status] || '状态未知'
        }}</text>
      </view>
      <text class="hint"
        >版本 {{ saved.version }} · 正文版本 {{ saved.content_version }} · 创建
        {{ supportTime(saved.created_at, scope.timezone) }} · 身份
        {{ saved.data_identity }} / {{ saved.channel }}</text
      >
      <template v-if="saved.snapshot">
        <text class="section-title"
          >正文 v{{ shownVersion }} ·
          {{ outcomeLabel(saved.snapshot.conclusion.outcome) }}</text
        >
        <text>{{ saved.snapshot.conclusion.note }}</text>
        <text class="hint"
          >存档范围
          {{
            supportTime(
              saved.snapshot.result.scope.start_at,
              saved.snapshot.result.scope.timezone,
            )
          }}
          至
          {{
            supportTime(
              saved.snapshot.result.scope.end_at,
              saved.snapshot.result.scope.timezone,
            )
          }}
          （结束不含，{{ saved.snapshot.result.scope.timezone }}）</text
        >
        <text
          v-for="item in saved.snapshot.blockers"
          :key="item"
          class="error"
          >{{ item }}</text
        >
        <button
          v-if="isCurrentVersion(saved, shownVersion)"
          :disabled="busy"
          @tap="begin(saved)"
        >
          修订并重新核对
        </button>
      </template>
      <text v-else class="muted">正文及全部历史依据已清除。</text>
      <button :disabled="busy" @tap="readCurrent">
        回读当前来源、费用与规则（不更新历史）
      </button>
    </view>
    <view v-if="saved?.history.length" class="card">
      <text class="section-title">结论历史（{{ saved.history.length }}）</text>
      <view v-for="entry in saved.history" :key="entry.version" class="record">
        <text
          >{{ historyLabel(entry.version, entry.action, entry.created_at) }}
          <template v-if="entry.conclusion"
            >· {{ outcomeLabel(entry.conclusion.outcome) }}</template
          ></text
        >
        <button
          v-if="entry.conclusion"
          :disabled="busy"
          @tap="perform(() => show(saved!.id, entry.version))"
        >
          读取 v{{ entry.version }} 依据
        </button>
      </view>
    </view>
    <view v-if="readBack" class="card">
      <text class="section-title">当前依据回读 · 尚未重新确认</text>
      <text class="hint"
        >此次读取不会更新历史结论；来源、同范围费用或规则变更后必须重新确认。</text
      >
      <text
        >{{ outcomeLabel(readBack.snapshot.conclusion.outcome) }} ·
        {{ readBack.snapshot.conclusion.note }}</text
      >
      <text
        v-for="total in readBack.snapshot.result.totals"
        :key="`rb-${total.currency}-${total.entry_type}`"
        >{{ total.currency }} ·
        {{ entryTypes[total.entry_type] || total.entry_type }}：
        {{ trimmedAmount(total.amount) }} （{{ total.count }} 笔）</text
      >
      <text
        v-for="item in readBack.snapshot.blockers"
        :key="`rbb-${item}`"
        class="error"
        >{{ item }}</text
      >
    </view>
    <view v-if="saved && saved.status !== 'cleared'" class="card">
      <text class="section-title">结论处理</text>
      <text class="hint"
        >撤销后可查看历史；清除会擦除这份存档所有版本的说明和依据，无法恢复。</text
      >
      <text v-if="!actions.length" class="muted"
        >当前状态没有可用的结论处理动作。</text
      >
      <template v-else>
        <picker
          :range="actions.map((action) => controls[action])"
          :value="Math.max(0, actions.indexOf(controlAction))"
          :disabled="busy"
          @change="pickControlAction"
          ><view class="select"
            >处理：{{ controls[controlAction] }}</view
          ></picker
        >
        <checkbox-group @change="toggleControl">
          <label class="label"
            ><checkbox
              value="control"
              :checked="controlConfirmed"
              :disabled="busy"
            />我确认处理此版本结论及上述影响</label
          >
        </checkbox-group>
        <button
          class="danger"
          :disabled="busy || !controlConfirmed"
          @tap="control()"
        >
          确认处理结论
        </button>
      </template>
    </view>
    <view v-if="saved && !canEdit(saved)" class="card">
      <text class="hint"
        >已撤销或已清除的存档不提供修订；请新建核对结论后重新核对。</text
      >
    </view>
  </view>
</template>
