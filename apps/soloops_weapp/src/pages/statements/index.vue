<template>
  <PageShell
    title="渠道账单与费用核对"
    subtitle="账单金额为绝对金额，由收支类型说明含义；费用编号与金额逐条对照，差异单独列出。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <FactLine label="所属店铺" :value="shopName" />
    <FactLine label="业务时区" :value="zone" />

    <text class="section-title">核对范围</text>
    <view class="field">
      <text class="field__label">数据身份</text>
      <picker mode="selector" :range="identityOptions" range-key="label" :value="identityIndex" @change="identity = identityOptions[Number(pickerValue($event))]?.key ?? 'user_import'">
        <view class="field__picker">{{ labelOf(importIdentities, identity) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">来源渠道</text>
      <picker mode="selector" :range="channelOptions" range-key="label" :value="channelIndex" @change="channel = channelOptions[Number(pickerValue($event))]?.key ?? 'generic'">
        <view class="field__picker">{{ labelOf(importChannels, channel) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">开始日期</text>
      <picker mode="date" :value="startDay" @change="startDay = pickerValue($event)">
        <view class="field__picker">{{ startDay === '' ? '请选择开始日期' : startDay }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">开始时间</text>
      <picker mode="time" :value="startClock" @change="startClock = pickerValue($event)">
        <view class="field__picker">{{ startClock }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">结束日期（区间为 [开始, 结束)）</text>
      <picker mode="date" :value="endDay" @change="endDay = pickerValue($event)">
        <view class="field__picker">{{ endDay === '' ? '请选择结束日期' : endDay }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">结束时间</text>
      <picker mode="time" :value="endClock" @change="endClock = pickerValue($event)">
        <view class="field__picker">{{ endClock }}</view>
      </picker>
    </view>
    <view class="row">
      <ActionButton label="核对账单与费用" variant="primary" :disabled="busy" @tap="calculate" />
      <ActionButton label="导入渠道账单" :disabled="busy" @tap="openPage('/pages/imports/index', { kind: 'statements' })" />
      <ActionButton label="费用映射规则" :disabled="busy" @tap="openPage('/pages/expenses/index')" />
      <ActionButton label="订单与账单核对" :disabled="busy" @tap="openPage('/pages/settlements/index')" />
    </view>

    <template v-if="result !== null">
      <text class="section-title">账单核对依据</text>
      <FactLine label="数据范围" :value="`${labelOf(importIdentities, result.scope.data_identity)} / ${labelOf(importChannels, result.scope.channel)}`" />
      <FactLine label="期间" :value="`${result.scope.start_at} 至 ${result.scope.end_at}`" :zone="zone" />
      <FactLine label="业务时区" :value="result.scope.timezone" />
      <FactLine label="来源 / 映射规则修订" :value="`${result.source_revision} / ${result.rule_revision}`" />
      <FactLine label="核对时间" :value="result.calculated_at" :zone="zone" />
      <FactLine label="待重核费用" :value="result.stale_expenses" />
      <FactLine label="撤销费用" :value="result.withdrawn_expenses" />
      <text v-for="check in result.checks ?? []" :key="check" class="hint">{{ check }}</text>

      <text class="section-title">分币种、分类型金额</text>
      <view v-for="total in result.totals ?? []" :key="`${total.currency}:${total.entry_type}`" class="card">
        <text class="card__title">{{ total.currency }} · {{ labelOf(entryTypes, total.entry_type) }}</text>
        <text class="hint">{{ total.count }} 行</text>
        <FactLine label="金额" :value="moneyText(total.amount, total.currency)" />
      </view>
      <view v-if="(result.totals ?? []).length === 0" class="card">
        <text class="hint">当前范围没有账单行。</text>
      </view>

      <text class="section-title">费用凭据匹配</text>
      <view v-for="comparison in result.comparisons ?? []" :key="comparison.evidence_ref" class="card">
        <text class="card__title">{{ comparison.evidence_ref }}</text>
        <text class="hint">{{ labelOf(comparisonStatuses, comparison.status) }}</text>
        <text class="hint">金额差异：{{ comparison.difference === null || comparison.difference === undefined ? '无法确定' : comparison.difference }}</text>
        <text class="hint">关联账单行：{{ (comparison.statement_ids ?? []).join(' / ') || '无' }}</text>
        <view v-for="expense in comparison.expenses ?? []" :key="expense.id">
          <text class="hint">
            {{ labelOf(expenseCategories, expense.category) }} · {{ expense.allocation === 'shop' ? '店铺未分摊' : '订单行费用' }}
          </text>
          <text class="hint">
            {{ expense.evidence_ref }} · {{ businessTimeText(expense.occurred_at, zone) }} · v{{ expense.version }} ·
            {{ moneyText(expense.amount, expense.currency) }}
          </text>
        </view>
      </view>
      <view v-if="(result.comparisons ?? []).length === 0" class="card">
        <text class="hint">当前范围没有可对照的费用凭据。</text>
      </view>

      <text class="section-title">费用类别映射</text>
      <view v-for="mapping in result.mappings ?? []" :key="`${mapping.statement_id}:${mapping.status}`" class="card">
        <text class="card__title">账单行 #{{ mapping.statement_id }}</text>
        <text class="hint">{{ mappingText(mapping) }}</text>
      </view>
      <view v-if="(result.mappings ?? []).length === 0" class="card">
        <text class="hint">当前范围没有费用行需要映射。</text>
      </view>

      <text class="section-title">全部账单明细与源行</text>
      <view v-for="item in result.statements ?? []" :key="item.id" class="card">
        <text class="card__title">{{ item.statement_id }} / {{ item.line_id }}</text>
        <FactLine label="收支类型" :value="labelOf(entryTypes, item.entry_type)" />
        <FactLine label="金额 / 币种" :value="moneyText(item.amount, item.currency)" />
        <FactLine label="发生时间" :value="item.occurred_at" :zone="result.scope.timezone" />
        <FactLine label="凭据编号" :value="item.evidence_ref" />
        <FactLine label="费用名称" :value="item.fee_name" />
        <FactLine label="结算编号" :value="item.settlement_id" />
        <FactLine label="订单号" :value="item.order_id" />
        <FactLine label="备注" :value="item.note" />
        <FactLine label="源行" :value="`${item.source.filename} · 第 ${item.source.row_number} 行 · 批次 ${item.source.batch_id}`" />
        <ActionButton label="查看来源与转换" :disabled="busy" @tap="openSource(item.source.row_id)" />
      </view>
    </template>

    <template v-if="source !== null">
      <text class="section-title">源行原始值与转换结果</text>
      <FactLine label="来源" :value="`${source.reference.filename} · 第 ${source.reference.row_number} 行（${source.batch_status}）`" />
      <view v-for="(value, key) in source.raw" :key="`raw:${key}`">
        <FactLine :label="`原始 ${key}`" :value="value" />
      </view>
      <view v-for="(value, key) in source.normalized" :key="`norm:${key}`">
        <FactLine :label="`转换后 ${key}`" :value="value" />
      </view>
      <ActionButton label="关闭来源面板" :disabled="busy" @tap="source = null" />
    </template>

    <text class="section-title">费用核对审阅</text>
    <FactLine label="审阅记录" :value="reviewRecord === null ? '尚未保存审阅' : `#${reviewRecord.id} · v${reviewRecord.version} · ${labelOf(expenseStatuses, reviewRecord.status)}`" />
    <view class="row">
      <ActionButton v-if="reviewRecord" label="回读最新存档" :disabled="busy" @tap="openReview(reviewRecord.id)" />
      <ActionButton label="用当前来源复核" :disabled="busy || reviewRecord === null" @tap="reloadCurrent" />
      <ActionButton label="新建审阅记录" :disabled="busy" @tap="resetReview" />
    </view>
    <view class="field">
      <text class="field__label">审阅结论</text>
      <picker mode="selector" :range="outcomeOptions" range-key="label" :value="outcomeIndex" @change="outcome = outcomeOptions[Number(pickerValue($event))]?.key ?? 'pending'">
        <view class="field__picker">{{ labelOf(reviewOutcomes, outcome) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">人工审阅说明与差异依据</text>
      <input class="field__input" :value="reviewNote" :disabled="busy || pendingReview" @input="reviewNote = inputValue($event)" />
    </view>
    <view class="row">
      <ActionButton label="预览结论与证据" :disabled="busy" @tap="previewReview" />
    </view>
    <template v-if="reviewPreview !== null">
      <FactLine label="预览来源修订" :value="reviewPreview.snapshot.expense_revision" />
      <FactLine label="预览结论" :value="labelOf(reviewOutcomes, reviewPreview.snapshot.conclusion.outcome)" />
      <FactLine label="预览说明" :value="reviewPreview.snapshot.conclusion.note" />
      <text v-for="blocker in reviewPreview.snapshot.blockers ?? []" :key="blocker" class="warn">{{ blocker }}</text>
      <view class="card" @tap="reviewConfirmed = !reviewConfirmed">
        <text class="chip" :class="{ 'chip--active': reviewConfirmed }">
          {{ reviewConfirmed ? '已核对' : '未核对' }} · 已核对以上金额、来源、差异与待核事项
        </text>
      </view>
      <text v-if="pendingReview" class="warn">写入结果待确认，请核对同次请求。</text>
      <view class="row">
        <ActionButton
          :label="pendingReview ? '核对同次写入' : '保存审阅版本'"
          variant="primary"
          :disabled="busy || (!reviewConfirmed && !pendingReview)"
          @tap="saveReview"
        />
        <ActionButton v-if="reviewRecord" label="撤销审阅" :disabled="busy" @tap="controlReview('withdraw')" />
        <ActionButton v-if="reviewRecord" label="清除审阅正文" :disabled="busy" @tap="controlReview('clear')" />
      </view>
    </template>
    <template v-if="reviewRecord !== null">
      <text class="section-title">审阅版本历史</text>
      <view v-for="history in reviewRecord.history ?? []" :key="history.version" class="card">
        <text class="card__title">版本 {{ history.version }} · {{ history.action }}</text>
        <text class="hint">{{ businessTimeText(history.created_at, zone) }}</text>
        <FactLine v-if="history.conclusion" label="结论" :value="labelOf(reviewOutcomes, history.conclusion.outcome)" />
        <FactLine v-if="history.conclusion" label="说明" :value="history.conclusion.note" />
        <text v-else class="hint">无正文</text>
      </view>
    </template>

    <text class="section-title">已保存的审阅</text>
    <FactLine label="列表范围" :value="`${labelOf(importIdentities, identity)} / ${labelOf(importChannels, channel)}`" />
    <view class="row">
      <ActionButton label="刷新审阅历史" :disabled="busy" @tap="load" />
    </view>
    <view v-if="reviews.length === 0 && !busy" class="card">
      <text class="hint">当前身份与渠道下暂无审阅记录。</text>
    </view>
    <view v-for="item in reviews" :key="item.id" class="card">
      <text class="card__title">审阅 #{{ item.id }} · v{{ item.version }}</text>
      <text class="hint">{{ labelOf(expenseStatuses, item.status) }} · {{ businessTimeText(item.created_at, zone) }}</text>
      <text v-if="item.snapshot" class="hint">结论：{{ labelOf(reviewOutcomes, item.snapshot.conclusion.outcome) }}</text>
      <ActionButton label="打开审阅" :disabled="busy" @tap="openReview(item.id)" />
    </view>
    <ActionButton v-if="nextCursor !== null" label="加载更多审阅" :disabled="busy" @tap="loadMore" />
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 渠道账单与费用核对：期间与分币种汇总、费用凭据匹配与类别映射、来源回读，
 * 以及费用核对审阅的预览、保存、版本与清除。
 * 接口（均来自 contracts/ui-contract.json 的 r2.statements）：
 *   POST /api/shops/{shop_id}/statements/reconcile
 *   POST /api/shops/{shop_id}/statement-reviews/preview
 *   POST /api/shops/{shop_id}/statement-reviews
 *   GET  /api/shops/{shop_id}/statement-reviews
 *   GET  /api/shops/{shop_id}/statement-reviews/{review_id}
 *   GET  /api/shops/{shop_id}/statement-reviews/{review_id}/current
 *   POST /api/shops/{shop_id}/statement-reviews/{review_id}/{action}   （withdraw / clear）
 *   GET  /api/shops/{shop_id}/analytics/sources/{row_id}
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import ActionButton from '../../ui/ActionButton.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import { ApiError, apiGet, apiPost, asObject, asRows, newRequestId } from '../../core/api'
import { businessTimeText, isValidDate, moneyText, todayInZone, zonedIsoFromParts } from '../../core/format'
import { importChannels, importIdentities, labelOf } from '../../core/labels'
import { openPage } from '../../core/links'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

const entryTypes: Record<string, string> = {
  sale: '账单销售款',
  refund: '账单退款',
  fee: '账单费用',
  payout: '平台记载回款 · 到账待核',
}

const comparisonStatuses: Record<string, string> = {
  matched: '编号与金额一致',
  amount_difference: '金额差异',
  statement_only: '仅账单有记录',
  expense_only: '仅人工费用有记录',
  receipt_only: '仅到账登记有记录',
  ambiguous: '重复编号 · 待核',
  currency_mismatch: '币种不一致',
  missing_reference: '缺关联编号',
  pending: '待核实',
}

const expenseCategories: Record<string, string> = {
  shipping: '物流',
  packaging: '包装',
  storage: '仓储',
  platform: '平台服务',
  advertising: '广告',
  tax: '税费',
  other: '其他费用',
}

const expenseStatuses: Record<string, string> = {
  active: '当前有效',
  stale: '来源变化 · 待重核',
  withdrawn: '已撤销',
  cleared: '正文已清除',
}

const mappingStatuses: Record<string, string> = {
  mapped: '已按规则分类 · 业务待核',
  unmapped: '未匹配规则',
  ambiguous: '重复凭据或规则',
  currency_mismatch: '币种不一致',
  category_conflict: '与人工费用类别冲突',
}

const reviewOutcomes: Record<string, string> = {
  consistent: '所选口径内一致',
  differences_recorded: '金额差异已说明 · 待跟进',
  pending: '仍待核对',
}

interface SourceReference {
  batch_id: number
  row_id: number
  row_number: number
  filename: string
  imported_at: string
}

interface ExpenseScope {
  data_identity: string
  channel: string
  start_at: string
  end_at: string
  timezone: string
}

interface StatementItem {
  id: number
  statement_id: string
  line_id: string
  entry_type: string
  amount: string
  currency: string
  occurred_at: string
  evidence_ref: string
  fee_name: string
  settlement_id: string
  order_id: string
  note: string
  source: SourceReference
}

interface StatementTotal {
  currency: string
  entry_type: string
  amount: string
  count: number
}

interface MatchedExpense {
  id: number
  version: number
  label: string
  category: string
  allocation: string
  evidence_ref: string
  amount: string
  currency: string
  occurred_at: string
}

interface FeeComparison {
  evidence_ref: string
  status: string
  statement_ids: number[]
  expenses: MatchedExpense[]
  difference?: string | null
}

interface FeeMapping {
  statement_id: number
  status: string
  category?: string | null
  rule_id?: number | null
  rule_version?: number | null
}

interface StatementReconciliation {
  scope: ExpenseScope
  source_revision: number
  rule_revision: number
  calculated_at: string
  statements: StatementItem[]
  totals: StatementTotal[]
  comparisons: FeeComparison[]
  mappings: FeeMapping[]
  stale_expenses: number
  withdrawn_expenses: number
  checks: string[]
}

interface ReviewConclusion {
  outcome: string
  note: string
}

interface ReviewSnapshot {
  conclusion: ReviewConclusion
  result: StatementReconciliation
  expense_revision: number
  blockers: string[]
}

interface ReviewPreview {
  preview_hash: string
  snapshot: ReviewSnapshot
}

interface ReviewHistory {
  version: number
  action: string
  conclusion: ReviewConclusion | null
  created_at: string
}

interface ReviewSaved {
  id: number
  shop_id: number
  data_identity: string
  channel: string
  status: string
  version: number
  content_version: number
  created_at: string
  snapshot: ReviewSnapshot | null
  history: ReviewHistory[]
}

interface SourceOutput {
  reference: SourceReference
  batch_status: string
  raw: Record<string, unknown>
  normalized: Record<string, unknown>
}

const identity = ref('user_import')
const channel = ref('generic')
const startDay = ref('')
const startClock = ref('00:00')
const endDay = ref('')
const endClock = ref('23:59')
const result = ref<StatementReconciliation | null>(null)
const source = ref<SourceOutput | null>(null)
const reviews = ref<ReviewSaved[]>([])
const nextCursor = ref<number | null>(null)
const reviewRecord = ref<ReviewSaved | null>(null)
const reviewPreview = ref<ReviewPreview | null>(null)
const outcome = ref('pending')
const reviewNote = ref('')
const reviewConfirmed = ref(false)
const pendingReview = ref(false)
const pendingReviewKey = ref<string | null>(null)
const busy = ref(false)
const error = ref('')
const successText = ref('')
const ready = ref(false)

const zone = computed(() => shopTimezone())
const shopName = computed(() => state.shops.find((shop) => shop.id === state.shopId)?.name ?? '未知')
const identityOptions = computed(() => Object.entries(importIdentities).map(([key, label]) => ({ key, label })))
const identityIndex = computed(() => Math.max(0, Object.keys(importIdentities).indexOf(identity.value)))
const channelOptions = computed(() => Object.entries(importChannels).map(([key, label]) => ({ key, label })))
const channelIndex = computed(() => Math.max(0, Object.keys(importChannels).indexOf(channel.value)))
const outcomeOptions = computed(() => Object.entries(reviewOutcomes).map(([key, label]) => ({ key, label })))
const outcomeIndex = computed(() => Math.max(0, Object.keys(reviewOutcomes).indexOf(outcome.value)))

function success(text: string): void {
  successText.value = text
  void Taro.showToast({ title: text, icon: 'none' })
}

/** 写操作：断线/超时提示“结果未知，请回读”，不推断成功。 */
async function writeAction(action: () => Promise<void>, done: string, hint: string): Promise<void> {
  let unknown = false
  const message = await perform(async () => {
    try {
      await action()
    } catch (caught) {
      unknown = caught instanceof ApiError && caught.kind === 'network_unknown'
      throw caught
    }
  })
  if (message === '') {
    success(done)
    return
  }
  error.value = unknown ? `${message} 结果未知，请回读${hint}核对后再决定。` : message
}

function scopePayload(): ExpenseScope {
  if (!isValidDate(startDay.value) || !isValidDate(endDay.value)) {
    throw new Error('请选择合法的开始与结束日期。')
  }
  const start = zonedIsoFromParts(startDay.value, startClock.value, zone.value)
  const end = zonedIsoFromParts(endDay.value, endClock.value, zone.value)
  if (start === null || end === null) throw new Error('业务时间无法换算，请核对时区与时间。')
  return {
    data_identity: identity.value,
    channel: channel.value,
    start_at: start,
    end_at: end,
    timezone: zone.value,
  }
}

function mappingText(mapping: FeeMapping): string {
  const category = mapping.category === null || mapping.category === undefined
    ? '待分类'
    : labelOf(expenseCategories, mapping.category)
  const rule = mapping.rule_id === null || mapping.rule_id === undefined
    ? ''
    : ` · 规则 #${mapping.rule_id} v${mapping.rule_version ?? '未知'}`
  return `${labelOf(mappingStatuses, mapping.status)} · ${category}${rule}`
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  const today = todayInZone(zone.value)
  if (endDay.value === '' && today !== null) endDay.value = today
  if (startDay.value === '' && today !== null) startDay.value = today
  await load()
})

async function load(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    const page = asObject<{ items: ReviewSaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/statement-reviews'), {
        data_identity: identity.value,
        channel: channel.value,
      }),
    )
    reviews.value = asRows<ReviewSaved>(page?.items)
    nextCursor.value = page?.next_cursor ?? null
  })
  error.value = message
}

async function loadMore(): Promise<void> {
  const cursor = nextCursor.value
  if (cursor === null) return
  const message = await perform(async () => {
    const page = asObject<{ items: ReviewSaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/statement-reviews'), {
        data_identity: identity.value,
        channel: channel.value,
        before: cursor,
      }),
    )
    const incoming = asRows<ReviewSaved>(page?.items)
    reviews.value = [
      ...reviews.value,
      ...incoming.filter((item) => !reviews.value.some((old) => old.id === item.id)),
    ]
    nextCursor.value = page?.next_cursor ?? null
  })
  error.value = message
}

async function calculate(): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<StatementReconciliation>(
      await apiPost(shopPath('/statements/reconcile'), scopePayload()),
    )
    if (value === null) throw new Error('核对响应无法读取，请刷新重试。')
    result.value = value
  })
  if (message === '') success('账单与费用已核对，请确认差异与待重核费用。')
  else error.value = message
}

async function openSource(rowId: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<SourceOutput>(await apiGet(shopPath(`/analytics/sources/${rowId}`)))
    if (value === null) throw new Error('来源响应无法读取，请刷新重试。')
    source.value = value
  })
  error.value = message
}

function resetReview(): void {
  reviewRecord.value = null
  reviewPreview.value = null
  reviewConfirmed.value = false
  pendingReview.value = false
  pendingReviewKey.value = null
  outcome.value = 'pending'
  reviewNote.value = ''
}

async function openReview(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<ReviewSaved>(await apiGet(shopPath(`/statement-reviews/${id}`)))
    if (value === null) throw new Error('审阅响应无法读取，请刷新重试。')
    reviewRecord.value = value
    reviewPreview.value = null
    reviewConfirmed.value = false
    pendingReview.value = false
    pendingReviewKey.value = null
    if (value.snapshot !== null) {
      outcome.value = value.snapshot.conclusion.outcome
      reviewNote.value = value.snapshot.conclusion.note
    }
    success('审阅记录与证据快照已回读。')
  })
  error.value = message
}

/** 用当前来源复核：读取 current，拿到服务端最新证据与预览。 */
async function reloadCurrent(): Promise<void> {
  const current = reviewRecord.value
  if (current === null) return
  const message = await perform(async () => {
    const value = asObject<{ record: ReviewSaved; preview: ReviewPreview | null }>(
      await apiGet(shopPath(`/statement-reviews/${current.id}/current`)),
    )
    if (value === null) throw new Error('回读响应无法读取，请刷新重试。')
    reviewRecord.value = value.record
    reviewPreview.value = value.preview
    reviewConfirmed.value = false
    if (value.record.snapshot !== null) {
      outcome.value = value.record.snapshot.conclusion.outcome
    }
  })
  error.value = message
}

async function previewReview(): Promise<void> {
  const message = await perform(async () => {
    if (result.value === null && reviewRecord.value === null) {
      throw new Error('请先运行核对，或打开一个已有审阅记录。')
    }
    if (reviewNote.value.trim() === '') throw new Error('请填写人工审阅说明与差异依据。')
    const value = asObject<ReviewPreview>(
      await apiPost(shopPath('/statement-reviews/preview'), {
        scope: scopePayload(),
        review_id: reviewRecord.value?.id ?? null,
        version: reviewRecord.value?.version ?? 0,
        conclusion: { outcome: outcome.value, note: reviewNote.value.trim() },
      }),
    )
    if (value === null) throw new Error('预览响应无法读取，请刷新后重试。')
    reviewPreview.value = value
    reviewConfirmed.value = false
  })
  error.value = message
}

async function saveReview(): Promise<void> {
  const preview = reviewPreview.value
  if (preview === null) return
  if (pendingReview.value && reviewRecord.value !== null) {
    await openReview(reviewRecord.value.id)
    return
  }
  const key = pendingReviewKey.value ?? newRequestId()
  pendingReviewKey.value = key
  await writeAction(async () => {
    const value = asObject<ReviewSaved>(
      await apiPost(shopPath('/statement-reviews'), {
        scope: preview.snapshot.result.scope,
        review_id: reviewRecord.value?.id ?? null,
        version: reviewRecord.value?.version ?? 0,
        conclusion: preview.snapshot.conclusion,
        preview_hash: preview.preview_hash,
        request_id: key,
        confirm: true,
      }),
    )
    if (value === null) throw new Error('保存响应无法读取，请到审阅历史回读核对。')
    pendingReview.value = false
    pendingReviewKey.value = null
    reviewRecord.value = value
    reviewPreview.value = null
    reviewConfirmed.value = false
    await load()
  }, '审阅记录与证据快照已保存。', '审阅历史')
}

async function controlReview(action: 'withdraw' | 'clear'): Promise<void> {
  const current = reviewRecord.value
  if (current === null) return
  const modal = await Taro.showModal({
    title: action === 'clear' ? '清除审阅正文' : '撤销审阅',
    content: action === 'clear' ? '清除本记录及历史快照正文，无法恢复。' : '撤销人工结论；版本依据仍可回读。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<ReviewSaved>(
      await apiPost(shopPath(`/statement-reviews/${current.id}/${action}`), {
        request_id: newRequestId(),
        version: current.version,
        confirm: true,
      }),
    )
    if (value !== null) reviewRecord.value = value
    await load()
  }, '审阅状态已更新。', '审阅历史')
}
</script>
