<template>
  <PageShell
    title="订单账单核对"
    subtitle="按订单号匹配订单行与销售 / 退款账单；金额组成无法确认时只列差异待核，不推算金额。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="calculate"
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
    <view class="field">
      <text class="field__label">销售款可比口径</text>
      <picker mode="selector" :range="basisOptions" range-key="label" :value="basisIndex" @change="setBasis($event)">
        <view class="field__picker">{{ labelOf(basisLabels, saleBasis) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">两侧原文件金额组成依据（选择可比口径时必填，最多 500 字）</text>
      <input class="field__input" :value="basisNote" :disabled="busy" @input="basisNote = inputValue($event)" />
    </view>
    <view class="row">
      <ActionButton label="匹配订单与账单" variant="primary" :disabled="busy" @tap="calculate" />
      <ActionButton label="导入订单行" :disabled="busy" @tap="openPage('/pages/imports/index', { kind: 'orders' })" />
      <ActionButton label="导入渠道账单" :disabled="busy" @tap="openPage('/pages/imports/index', { kind: 'statements' })" />
      <ActionButton label="渠道账单与费用核对" :disabled="busy" @tap="openPage('/pages/statements/index')" />
    </view>
    <text class="hint">金额相同的分组按订单行逐项核对；任何未确认口径、币种或状态都不会被当作一致。</text>

    <template v-if="result !== null">
      <text class="section-title">核对依据</text>
      <FactLine label="数据范围" :value="`${labelOf(importIdentities, result.scope.data_identity)} / ${labelOf(importChannels, result.scope.channel)}`" />
      <FactLine label="期间" :value="`${result.scope.start_at} 至 ${result.scope.end_at}`" :zone="zone" />
      <FactLine label="业务时区" :value="result.scope.timezone" />
      <FactLine label="销售口径" :value="labelOf(basisLabels, result.scope.sale_basis)" />
      <FactLine label="口径依据" :value="result.scope.basis_note" />
      <FactLine label="来源修订" :value="result.source_revision" />
      <FactLine label="核对时间" :value="result.calculated_at" :zone="zone" />
      <FactLine label="来源覆盖完整性" :value="coverageText" />
      <text v-for="check in result.checks ?? []" :key="check" class="hint">{{ check }}</text>

      <text class="section-title">匹配与差异（{{ comparisons.length }} 组）</text>
      <view v-for="comparison in comparisons" :key="`${comparison.order_id}:${comparison.entry_type}`" class="card">
        <text class="card__title">
          {{ comparison.order_id === '' ? '缺少来源订单号' : comparison.order_id }} ·
          {{ labelOf(entryTypes, comparison.entry_type) }}
        </text>
        <text class="hint">{{ labelOf(comparisonStatuses, comparison.status) }}</text>
        <FactLine label="订单可比金额" :value="comparison.order_amount === null || comparison.order_amount === undefined ? '未知' : moneyText(comparison.order_amount, comparison.currency)" />
        <FactLine label="差额（账单 − 订单）" :value="comparison.difference === null || comparison.difference === undefined ? '未知' : moneyText(comparison.difference, comparison.currency)" />
        <FactLine label="关联账单行" :value="(comparison.statement_ids ?? []).join(' / ')" />
        <FactLine label="关联订单行" :value="(comparison.order_line_ids ?? []).join(' / ')" />
        <text v-for="reason in comparison.reasons ?? []" :key="reason" class="warn">{{ reasonText(reason) }}</text>
        <text v-if="(comparison.reasons ?? []).length === 0" class="hint">两侧编号、币种与状态均已具备可比条件。</text>
        <view v-for="order in ordersOf(comparison)" :key="`order:${order.id}`" class="card">
          <text class="card__title">{{ order.order_id }} / {{ order.line_id }} · {{ order.sku }}</text>
          <text class="hint">{{ order.quantity }} 件 · {{ labelOf(orderStatuses, order.status) }} · {{ order.in_window ? '在所选期间内' : '期间外关联记录' }}</text>
          <FactLine label="下单时间" :value="order.ordered_at" :zone="result.scope.timezone" />
          <FactLine label="折扣前单价" :value="moneyText(order.unit_price, order.currency)" />
          <FactLine label="行折扣" :value="order.discount === null || order.discount === undefined ? '未知' : moneyText(order.discount, order.currency)" />
          <FactLine label="累计行退款" :value="order.refund === null || order.refund === undefined ? '未知' : moneyText(order.refund, order.currency)" />
          <FactLine label="履约状态" :value="labelOf(fulfillmentStatuses, order.fulfillment_status)" />
          <SourceEvidence :source="order.source" :zone="result.scope.timezone" />
        </view>
        <view v-for="item in statementsOf(comparison)" :key="`statement:${item.id}`" class="card">
          <text class="card__title">{{ item.statement_id }} / {{ item.line_id }}</text>
          <text class="hint">{{ labelOf(entryTypes, item.entry_type) }} · {{ item.in_window ? '在所选期间内' : '期间外关联记录' }}</text>
          <FactLine label="金额 / 币种" :value="moneyText(item.amount, item.currency)" />
          <FactLine label="发生时间" :value="item.occurred_at" :zone="result.scope.timezone" />
          <FactLine label="凭据编号" :value="item.evidence_ref" />
          <FactLine label="费用名称" :value="item.fee_name" />
          <FactLine label="结算编号" :value="item.settlement_id" />
          <SourceEvidence :source="item.source" :zone="result.scope.timezone" />
        </view>
      </view>
      <view v-if="comparisons.length === 0" class="card">
        <text class="hint">当前范围没有可核对的订单与账单组合。可调整期间或先导入订单行与渠道账单。</text>
      </view>

      <text class="section-title">全部订单行（{{ (result.orders ?? []).length }}）</text>
      <view v-for="order in result.orders ?? []" :key="order.id" class="card">
        <text class="card__title">{{ order.order_id }} / {{ order.line_id }} · {{ order.sku }}</text>
        <text class="hint">{{ order.in_window ? '在所选期间内' : '期间外关联记录' }} · {{ labelOf(orderStatuses, order.status) }}</text>
        <FactLine label="下单时间" :value="order.ordered_at" :zone="result.scope.timezone" />
        <FactLine label="折扣前单价 × 数量" :value="`${moneyText(order.unit_price, order.currency)} × ${order.quantity}`" />
        <FactLine label="行折扣" :value="order.discount === null || order.discount === undefined ? '未知' : moneyText(order.discount, order.currency)" />
        <FactLine label="累计行退款" :value="order.refund === null || order.refund === undefined ? '未知' : moneyText(order.refund, order.currency)" />
        <SourceEvidence :source="order.source" :zone="result.scope.timezone" />
      </view>
      <view v-if="(result.orders ?? []).length === 0" class="card">
        <text class="hint">当前范围没有订单行来源。</text>
      </view>

      <text class="section-title">全部销售 / 退款账单（{{ (result.statements ?? []).length }}）</text>
      <view v-for="item in result.statements ?? []" :key="item.id" class="card">
        <text class="card__title">{{ item.statement_id }} / {{ item.line_id }}</text>
        <text class="hint">{{ labelOf(entryTypes, item.entry_type) }} · {{ item.in_window ? '在所选期间内' : '期间外关联记录' }}</text>
        <FactLine label="金额 / 币种" :value="moneyText(item.amount, item.currency)" />
        <FactLine label="发生时间" :value="item.occurred_at" :zone="result.scope.timezone" />
        <FactLine label="订单号" :value="item.order_id" />
        <FactLine label="凭据编号" :value="item.evidence_ref" />
        <SourceEvidence :source="item.source" :zone="result.scope.timezone" />
      </view>
      <view v-if="(result.statements ?? []).length === 0" class="card">
        <text class="hint">当前范围没有销售或退款账单来源。</text>
      </view>

      <text class="section-title">说明</text>
      <text class="hint">本页只读取来源并给出比对结果，不写入任何记录；差异需在渠道账单与费用核对页保存审阅结论。</text>
    </template>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 订单账单核对：按订单号匹配订单行与销售 / 退款账单，逐组列出差异与待核原因。
 * 接口（均来自 contracts/ui-contract.json 的 r2.order_reconciliation）：
 *   POST /api/shops/{shop_id}/statements/orders/reconcile
 *   GET  /api/shops/{shop_id}/analytics/sources/{row_id}（来源证据由 SourceEvidence 的父页面回读口径）
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import ActionButton from '../../ui/ActionButton.vue'
import SourceEvidence from '../../ui/SourceEvidence.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import { apiPost, asObject } from '../../core/api'
import { isValidDate, moneyText, todayInZone, zonedIsoFromParts } from '../../core/format'
import { importChannels, importIdentities, labelOf } from '../../core/labels'
import { openPage } from '../../core/links'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

/** 销售款可比口径：与后端 OrderReconciliationScope.sale_basis 一致。 */
const basisLabels: Record<string, string> = {
  unknown: '金额组成尚未确认 · 只列差异待核',
  merchandise_after_discount: '退款前折后商品款 · 不含运费税费及其他调整',
}

/** 收支类型：与 Flutter finance_common.dart 的 entryTypes 一致。 */
const entryTypes: Record<string, string> = {
  sale: '账单销售款',
  refund: '账单退款',
}

/** 订单与账单分组的比对状态（后端 OrderComparison.status）。 */
const comparisonStatuses: Record<string, string> = {
  matched: '所选口径内金额相同',
  amount_difference: '金额差异 · 需核对来源',
  pending: '待核实 · 不予比较',
}

/** 待核原因：与 Flutter orderReconciliationPage 的 orderReasons 逐条对齐。 */
const reasonTexts: Record<string, string> = {
  missing_order_reference: '账单缺少来源订单号，需补充稳定关联编号。',
  order_not_imported: '当前导入范围没有此订单，文件覆盖仍待核对。',
  statement_not_imported: '当前导入范围没有此类型账单，需核查来源覆盖。',
  multiple_order_lines: '订单有多行，账单未提供可核验的行归属。',
  multiple_statement_lines: '同订单有多笔同类账单，拆分、重复或调整关系待核。',
  outside_window: '存在期间外关联来源，请核实跨期关系。',
  currency_mismatch: '两侧币种不同，缺少已确认换汇依据。',
  order_status_uncomparable: '未付款、取消或测试状态不支持销售金额比较。',
  refund_transaction_unknown: '累计行退款缺逐笔编号、时间、金额组成及支付状态，差额未知。',
  refund_amount_unknown: '订单行退款金额未知。',
  sale_basis_unknown: '销售款金额组成未知，需核实两侧原文件口径。',
  discount_unknown: '订单行折扣未知，无法计算折后商品款。',
  different_local_date: '账单与订单当地日期不同，时间归属待核。',
}

/** 订单状态与履约状态：未命中的取值保留原值展示。 */
const orderStatuses: Record<string, string> = {
  pending: '未付款',
  paid: '已付款',
  partially_refunded: '部分退款',
  refunded: '已退款',
  cancelled: '已取消',
  test: '测试数据',
}

const fulfillmentStatuses: Record<string, string> = {
  unfulfilled: '未发货',
  partial: '部分发货',
  fulfilled: '已发货',
  unknown: '履约状态未知',
}

interface SourceReference {
  origin?: string
  batch_id: number
  row_id: number
  row_number: number
  filename: string
  sheet_name?: string
  exported_at?: string | null
  imported_at?: string
  data_identity?: string
}

interface ReconciliationOrder {
  id: number
  order_id: string
  line_id: string
  sku: string
  quantity: number
  unit_price: string
  currency: string
  ordered_at: string
  status: string
  discount?: string | null
  refund?: string | null
  fulfillment_status?: string
  in_window: boolean
  source: SourceReference
}

interface ReconciliationStatement {
  id: number
  statement_id: string
  line_id: string
  entry_type: string
  amount: string
  currency: string
  occurred_at: string
  evidence_ref?: string
  fee_name?: string
  settlement_id?: string
  order_id?: string
  note?: string
  in_window: boolean
  source: SourceReference
}

interface OrderComparison {
  order_id: string
  entry_type: string
  statement_ids: number[]
  order_line_ids: number[]
  status: string
  reasons: string[]
  currency?: string | null
  order_amount?: string | null
  difference?: string | null
}

interface OrderReconciliation {
  scope: {
    data_identity: string
    channel: string
    start_at: string
    end_at: string
    timezone: string
    sale_basis: string
    basis_note: string
  }
  source_revision: number
  calculated_at: string
  coverage: string
  orders: ReconciliationOrder[]
  statements: ReconciliationStatement[]
  comparisons: OrderComparison[]
  checks: string[]
}

const identity = ref('user_import')
const channel = ref('generic')
const startDay = ref('')
const startClock = ref('00:00')
const endDay = ref('')
const endClock = ref('23:59')
const saleBasis = ref('unknown')
const basisNote = ref('')
const result = ref<OrderReconciliation | null>(null)
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
const basisOptions = computed(() => Object.entries(basisLabels).map(([key, label]) => ({ key, label })))
const basisIndex = computed(() => Math.max(0, Object.keys(basisLabels).indexOf(saleBasis.value)))
const comparisons = computed(() => result.value?.comparisons ?? [])
const coverageText = computed(() =>
  result.value === null ? '未知' : labelOf({ unknown: '未知' }, result.value.coverage),
)

/** 分组明细按服务端返回的订单行 / 账单行 ID 关联，不在客户端重新匹配。 */
const orderIndex = computed(() => new Map((result.value?.orders ?? []).map((order) => [order.id, order])))
const statementIndex = computed(() => new Map((result.value?.statements ?? []).map((item) => [item.id, item])))

function success(text: string): void {
  successText.value = text
  void Taro.showToast({ title: text, icon: 'none' })
}

function reasonText(reason: string): string {
  return reasonTexts[reason] ?? `未识别的待核原因：${reason}`
}

function ordersOf(comparison: OrderComparison): ReconciliationOrder[] {
  return (comparison.order_line_ids ?? [])
    .map((id) => orderIndex.value.get(id))
    .filter((order): order is ReconciliationOrder => order !== undefined)
}

function statementsOf(comparison: OrderComparison): ReconciliationStatement[] {
  return (comparison.statement_ids ?? [])
    .map((id) => statementIndex.value.get(id))
    .filter((item): item is ReconciliationStatement => item !== undefined)
}

function setBasis(event: unknown): void {
  saleBasis.value = basisOptions.value[Number(pickerValue(event))]?.key ?? 'unknown'
}

/** 范围载荷：服务端要求带偏移的时刻，客户端只做换算不做金额计算。 */
function scopePayload(): Record<string, string> {
  if (!isValidDate(startDay.value) || !isValidDate(endDay.value)) {
    throw new Error('请选择合法的开始与结束日期。')
  }
  const start = zonedIsoFromParts(startDay.value, startClock.value, zone.value)
  const end = zonedIsoFromParts(endDay.value, endClock.value, zone.value)
  if (start === null || end === null) throw new Error('业务时间无法换算，请核对时区与时间。')
  if (saleBasis.value !== 'unknown' && basisNote.value.trim() === '') {
    throw new Error('选择可比销售口径时，请填写两侧原文件的金额组成依据。')
  }
  if (basisNote.value.trim().length > 500) throw new Error('口径依据最多 500 字。')
  return {
    data_identity: identity.value,
    channel: channel.value,
    start_at: start,
    end_at: end,
    timezone: zone.value,
    sale_basis: saleBasis.value,
    basis_note: basisNote.value.trim(),
  }
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  const today = todayInZone(zone.value)
  if (endDay.value === '' && today !== null) endDay.value = today
  if (startDay.value === '' && today !== null) startDay.value = today
})

async function calculate(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    const value = asObject<OrderReconciliation>(
      await apiPost(shopPath('/statements/orders/reconcile'), scopePayload()),
    )
    if (value === null) throw new Error('核对响应无法读取，请刷新重试。')
    result.value = value
  })
  if (message === '') success('订单与账单已按订单号匹配，请核对差异与待核原因。')
  else error.value = message
}
</script>
