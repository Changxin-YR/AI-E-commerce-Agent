<template>
  <PageShell
    title="实际费用"
    subtitle="人工费用按单店、单身份与单渠道记录；与账单核对前不视为已确认。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <FactLine label="所属店铺" :value="shopName" />
    <FactLine label="业务时区" :value="zone" />

    <text class="section-title">查询条件</text>
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
      <text class="field__label">结束日期（不含次日零点之后的记录，区间为 [开始, 结束)）</text>
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
      <ActionButton label="查询费用" variant="primary" :disabled="busy" @tap="load" />
      <ActionButton label="按期间汇总" :disabled="busy" @tap="loadSummary" />
      <ActionButton label="录入费用" :disabled="busy" @tap="startCreate" />
      <ActionButton label="费用映射规则" :disabled="busy" @tap="loadRules" />
    </view>

    <template v-if="summary !== null">
      <text class="section-title">期间费用 · 按币种分别汇总</text>
      <FactLine label="有效笔数" :value="summary.included_count" />
      <FactLine label="来源变化笔数" :value="summary.stale_count" />
      <FactLine label="已撤销笔数" :value="summary.withdrawn_count" />
      <view v-for="total in summary.totals ?? []" :key="`${total.currency}:${total.category}:${total.allocation}`" class="card">
        <text class="card__title">{{ total.currency }} · {{ labelOf(expenseCategories, total.category) }}</text>
        <text class="hint">{{ total.allocation === 'shop' ? '店铺未分摊' : '订单行' }} · {{ total.count }} 笔</text>
        <FactLine label="金额合计" :value="moneyText(total.amount, total.currency)" />
      </view>
      <text v-for="check in summary.checks ?? []" :key="check" class="hint">{{ check }}</text>
      <view v-if="(summary.totals ?? []).length === 0" class="card">
        <text class="hint">当前期间没有有效费用记录。</text>
      </view>
    </template>

    <text class="section-title">费用记录</text>
    <view v-if="records.length === 0 && !busy" class="card">
      <text class="hint">当前筛选没有费用记录。可以先录入一笔带凭据的费用。</text>
    </view>
    <view v-for="item in records" :key="item.id" class="card">
      <text class="card__title" @tap="openRecord(item.id)">
        #{{ item.id }} {{ item.snapshot === null ? '正文已清除' : factText(item.snapshot.content.label) }}
      </text>
      <text class="hint">
        {{ item.snapshot === null ? '正文已清除' : labelOf(expenseCategories, item.snapshot.content.category) }} ·
        {{ labelOf(expenseStatuses, item.status) }} · 版本 {{ item.version }} · {{ businessTimeText(item.created_at, zone) }}
      </text>
      <text v-if="item.snapshot !== null" class="hint">
        {{ moneyText(item.snapshot.content.amount, item.snapshot.content.currency) }} ·
        {{ item.snapshot.content.allocation === 'shop' ? '店铺未分摊' : '订单行' }}
      </text>
      <ActionButton label="打开费用详情" :disabled="busy" @tap="openRecord(item.id)" />
    </view>
    <ActionButton v-if="nextCursor !== null" label="加载更多记录" :disabled="busy" @tap="loadMore" />

    <template v-if="editing">
      <text class="section-title">{{ record === null ? '录入费用' : `费用 #${record.id}` }}</text>
      <FactLine label="数据身份 / 渠道" :value="`${labelOf(importIdentities, identity)} / ${labelOf(importChannels, channel)}`" />
      <FactLine v-if="record" label="状态" :value="labelOf(expenseStatuses, record.status)" />
      <view class="row">
        <ActionButton v-if="record" label="回读最新版本（替换表单）" :disabled="busy" @tap="openRecord(record.id)" />
      </view>
      <text v-if="pending" class="warn">上次写入结果待确认，表单已锁定。核对同次请求后再修改。</text>

      <view class="field">
        <text class="field__label">费用名称</text>
        <input class="field__input" :value="form.label" :disabled="busy || pending" @input="form.label = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">费用类别</text>
        <picker mode="selector" :range="categoryOptions" range-key="label" :value="categoryIndex" @change="form.category = categoryOptions[Number(pickerValue($event))]?.key ?? 'other'">
          <view class="field__picker">{{ labelOf(expenseCategories, form.category) }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">费用总额（须大于 0）</text>
        <input class="field__input" :value="form.amount" :disabled="busy || pending" @input="form.amount = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">币种</text>
        <input class="field__input" :value="form.currency" :disabled="busy || pending" @input="form.currency = inputValue($event).toUpperCase()" />
      </view>
      <view class="field">
        <text class="field__label">发生日期</text>
        <picker mode="date" :value="form.occurredDay" @change="form.occurredDay = pickerValue($event)">
          <view class="field__picker">{{ form.occurredDay === '' ? '请选择发生日期' : form.occurredDay }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">发生时间</text>
        <picker mode="time" :value="form.occurredClock" @change="form.occurredClock = pickerValue($event)">
          <view class="field__picker">{{ form.occurredClock }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">发生时区（IANA）</text>
        <input class="field__input" :value="form.timezone" :disabled="busy || pending" @input="form.timezone = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">凭据唯一编号</text>
        <input class="field__input" :value="form.evidenceRef" :disabled="busy || pending" @input="form.evidenceRef = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">凭据内容与核查依据</text>
        <input class="field__input" :value="form.evidenceNote" :disabled="busy || pending" @input="form.evidenceNote = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">录入或修订原因</text>
        <input class="field__input" :value="form.reason" :disabled="busy || pending" @input="form.reason = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">费用归属</text>
        <picker mode="selector" :range="allocationOptions" range-key="label" :value="allocationIndex" @change="setAllocation($event)">
          <view class="field__picker">{{ form.allocation === 'shop' ? '店铺费用 · 未分摊' : '整笔归属单一订单行' }}</view>
        </picker>
      </view>
      <template v-if="form.allocation === 'order_line'">
        <view class="field">
          <text class="field__label">订单号（精确匹配）</text>
          <input class="field__input" :value="orderQuery" :disabled="busy || pending" @input="orderQuery = inputValue($event)" />
        </view>
        <ActionButton label="查询当前订单行" :disabled="busy || pending" @tap="queryOrders" />
        <view v-for="order in orders" :key="order.id" class="card" @tap="chooseOrder(order)">
          <text class="card__title">{{ order.order_id }} / {{ order.line_id }} · {{ order.sku }}</text>
          <text class="hint">
            {{ order.currency }} · {{ order.status }} · {{ order.source.filename }} 第 {{ order.source.row_number }} 行
          </text>
          <text class="chip" :class="{ 'chip--active': form.orderLineId === order.id }">
            {{ form.orderLineId === order.id ? '已选择此行' : '选择此行' }}
          </text>
        </view>
        <FactLine label="来源修订" :value="ordersRevision" />
        <text v-if="orders.length === 0" class="hint">请先查询并重新选择当前订单行。</text>
      </template>
      <view class="card" @tap="toggleConfirmed">
        <text class="chip" :class="{ 'chip--active': form.confirmed }">
          {{ form.confirmed ? '已逐项确认' : '未确认' }} · 已核对凭据、金额和费用归属；此人工记录尚需与账单核对
        </text>
      </view>
      <view class="row">
        <ActionButton
          :label="pending ? '核对同次写入' : '保存费用版本'"
          variant="primary"
          :disabled="busy || (!form.confirmed && !pending)"
          @tap="saveRecord"
        />
        <ActionButton v-if="record" label="撤销费用" :disabled="busy" @tap="controlRecord('withdraw')" />
        <ActionButton v-if="record" label="清除正文与依据" :disabled="busy" @tap="controlRecord('clear')" />
        <ActionButton label="取消编辑" :disabled="busy" @tap="closeEdit" />
      </view>

      <template v-if="record">
        <text class="section-title">版本与依据历史</text>
        <view v-for="history in record.history ?? []" :key="history.version" class="card">
          <text class="card__title">版本 {{ history.version }} · {{ history.action }}</text>
          <text class="hint">{{ businessTimeText(history.created_at, zone) }}</text>
          <template v-if="history.snapshot">
            <FactLine label="费用名称" :value="history.snapshot.content.label" />
            <FactLine label="费用类别" :value="labelOf(expenseCategories, history.snapshot.content.category)" />
            <FactLine label="金额 / 币种" :value="moneyText(history.snapshot.content.amount, history.snapshot.content.currency)" />
            <FactLine label="发生时间" :value="`${history.snapshot.content.occurred_at} · ${history.snapshot.content.timezone}`" :zone="zone" />
            <FactLine label="凭据编号" :value="history.snapshot.content.evidence_ref" />
            <FactLine label="凭据依据" :value="history.snapshot.content.evidence_note" />
            <FactLine label="修订原因" :value="history.snapshot.content.reason" />
            <FactLine
              label="归属"
              :value="history.snapshot.content.allocation === 'shop'
                ? '店铺未分摊'
                : `订单 ${factText(history.snapshot.order_id)} / ${factText(history.snapshot.line_id)} · ${factText(history.snapshot.sku)}`"
            />
            <FactLine label="来源修订" :value="history.snapshot.content.expected_source_revision" />
          </template>
          <text v-else class="hint">正文已清除</text>
        </view>
        <text v-if="(record.history ?? []).length === 0" class="hint">服务端未返回版本历史。</text>
      </template>
    </template>

    <template v-if="rulesVisible">
      <text class="section-title">费用映射规则</text>
      <text class="hint">用账单中的费用名称映射类别。预览只比较所选期间；保存的规则作用于相同身份与渠道。</text>
      <view class="row">
        <ActionButton label="刷新规则列表" :disabled="busy" @tap="loadRules" />
        <ActionButton label="新建另一规则" :disabled="busy" @tap="resetRuleDraft" />
      </view>
      <view v-if="rules.length === 0 && !busy" class="card">
        <text class="hint">当前身份与渠道下暂无收费映射规则。</text>
      </view>
      <view v-for="rule in rules" :key="rule.id" class="card">
        <text class="card__title">#{{ rule.id }} {{ rule.content === null ? '正文已清除' : factText(rule.content.fee_name) }}</text>
        <text class="hint">
          {{ rule.content === null ? '待分类' : labelOf(expenseCategories, rule.content.category) }} ·
          版本 {{ rule.version }} · {{ labelOf(expenseStatuses, rule.status) }}
        </text>
        <ActionButton label="打开规则" :disabled="busy" @tap="openRule(rule.id)" />
      </view>

      <text class="section-title">{{ ruleRecord === null ? '新建规则' : `规则 #${ruleRecord.id}` }}</text>
      <FactLine label="当前规则" :value="ruleRecord === null ? '尚未选择规则' : `${factText(ruleRecord.content?.fee_name)} → ${labelOf(expenseCategories, ruleRecord.content?.category)}`" />
      <view class="row">
        <ActionButton v-if="ruleRecord" label="回读最新规则" :disabled="busy" @tap="openRule(ruleRecord.id)" />
      </view>
      <view class="field">
        <text class="field__label">账单费用名称（按服务端标准化后精确匹配）</text>
        <input class="field__input" :value="ruleForm.feeName" :disabled="busy" @input="ruleForm.feeName = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">归入类别</text>
        <picker mode="selector" :range="categoryOptions" range-key="label" :value="ruleCategoryIndex" @change="ruleForm.category = categoryOptions[Number(pickerValue($event))]?.key ?? 'other'">
          <view class="field__picker">{{ labelOf(expenseCategories, ruleForm.category) }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">分类与修订依据</text>
        <input class="field__input" :value="ruleForm.reason" :disabled="busy" @input="ruleForm.reason = inputValue($event)" />
      </view>
      <view class="row">
        <ActionButton label="预览映射变化" :disabled="busy" @tap="previewRule" />
      </view>
      <template v-if="rulePreview !== null">
        <text class="section-title">待确认的分类变化</text>
        <FactLine label="当前来源修订" :value="rulePreview.source_revision" />
        <FactLine label="账单行数" :value="rulePreview.statement_count" />
        <FactLine label="原规则" :value="rulePreview.previous === null ? '无' : `${rulePreview.previous.fee_name} → ${labelOf(expenseCategories, rulePreview.previous.category)}`" />
        <FactLine label="拟保存规则" :value="`${rulePreview.proposed.fee_name} → ${labelOf(expenseCategories, rulePreview.proposed.category)}`" />
        <view v-for="change in rulePreview.changes ?? []" :key="`${change.statement_id}:${change.fee_name}`" class="card">
          <text class="card__title">账单行 #{{ change.statement_id }} · {{ change.fee_name }}</text>
          <text class="hint">原：{{ mappingText(change.before) }}</text>
          <text class="hint">新：{{ mappingText(change.after) }}</text>
        </view>
        <view class="card" @tap="ruleConfirmed = !ruleConfirmed">
          <text class="chip" :class="{ 'chip--active': ruleConfirmed }">
            {{ ruleConfirmed ? '已核对' : '未核对' }} · 已核对受影响的账单、类别与依据
          </text>
        </view>
        <text v-if="pendingRule" class="warn">写入结果待确认。使用同一请求回查保存结果。</text>
        <view class="row">
          <ActionButton
            :label="pendingRule ? '核对同次写入' : '保存已预览规则'"
            variant="primary"
            :disabled="busy || (!ruleConfirmed && !pendingRule)"
            @tap="saveRule"
          />
          <ActionButton v-if="ruleRecord" label="撤销规则" :disabled="busy" @tap="controlRule('withdraw')" />
          <ActionButton v-if="ruleRecord" label="清除规则正文" :disabled="busy" @tap="controlRule('clear')" />
        </view>
        <template v-if="ruleRecord">
          <text class="section-title">规则版本历史</text>
          <view v-for="history in ruleRecord.history ?? []" :key="history.version" class="card">
            <text class="card__title">版本 {{ history.version }} · {{ history.action }}</text>
            <text class="hint">{{ businessTimeText(history.created_at, zone) }}</text>
            <FactLine v-if="history.content" label="费用名称 → 类别" :value="`${history.content.fee_name} → ${labelOf(expenseCategories, history.content.category)}`" />
            <FactLine v-if="history.content" label="依据" :value="history.content.reason" />
            <text v-else class="hint">正文已清除</text>
          </view>
        </template>
      </template>
    </template>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 实际费用：查询、按期间汇总、录入/修订/撤销/清除、订单归属选择与版本历史，
 * 并维护账单费用名称到费用类别的映射规则。
 * 接口（均来自 contracts/ui-contract.json 的 r2.expenses）：
 *   GET  /api/shops/{shop_id}/expenses          POST /api/shops/{shop_id}/expenses
 *   GET  /api/shops/{shop_id}/expenses/orders   POST /api/shops/{shop_id}/expenses/summary
 *   GET  /api/shops/{shop_id}/expenses/{expense_id}
 *   POST /api/shops/{shop_id}/expenses/{expense_id}
 *   POST /api/shops/{shop_id}/expenses/{expense_id}/{action}   （withdraw / clear）
 *   GET  /api/shops/{shop_id}/fee-rules         POST /api/shops/{shop_id}/fee-rules
 *   POST /api/shops/{shop_id}/fee-rules/preview GET /api/shops/{shop_id}/fee-rules/{rule_id}
 *   POST /api/shops/{shop_id}/fee-rules/{rule_id}/{action}     （withdraw / clear）
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import ActionButton from '../../ui/ActionButton.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import { ApiError, apiGet, apiPost, asObject, asRows, newRequestId } from '../../core/api'
import { businessTimeText, factText, isDecimalInput, isValidDate, moneyText, todayInZone, zonedIsoFromParts } from '../../core/format'
import { importChannels, importIdentities, labelOf } from '../../core/labels'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

/** 费用类别与状态标签：与 Flutter finance_common.dart 一致。 */
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

const allocationOptions = [
  { key: 'shop', label: '店铺费用 · 未分摊' },
  { key: 'order_line', label: '整笔归属单一订单行' },
]

interface SourceReference {
  batch_id: number
  row_id: number
  row_number: number
  filename: string
  imported_at: string
}

interface ExpenseContent {
  label: string
  category: string
  amount: string
  currency: string
  occurred_at: string
  timezone: string
  evidence_ref: string
  evidence_note: string
  allocation: string
  order_line_id?: number | null
  expected_source_row_id?: number | null
  expected_source_revision?: number | null
  reason: string
}

interface ExpenseSnapshot {
  content: ExpenseContent
  source?: SourceReference | null
  order_id?: string | null
  line_id?: string | null
  sku?: string | null
  order_status?: string | null
}

interface ExpenseHistory {
  version: number
  action: string
  created_at: string
  snapshot: ExpenseSnapshot | null
}

interface ExpenseSaved {
  id: number
  shop_id: number
  data_identity: string
  channel: string
  version: number
  status: string
  created_at: string
  snapshot: ExpenseSnapshot | null
  history: ExpenseHistory[]
}

interface ExpenseTotal {
  currency: string
  category: string
  allocation: string
  amount: string
  count: number
}

interface ExpenseSummary {
  scope: { data_identity: string; channel: string; start_at: string; end_at: string; timezone: string }
  totals: ExpenseTotal[]
  included_count: number
  stale_count: number
  withdrawn_count: number
  checks: string[]
}

interface ExpenseOrder {
  id: number
  order_id: string
  line_id: string
  sku: string
  currency: string
  status: string
  source: SourceReference
}

interface FeeRuleContent {
  fee_name: string
  category: string
  reason: string
}

interface FeeRuleHistory {
  version: number
  action: string
  content: FeeRuleContent | null
  created_at: string
}

interface FeeRuleSaved {
  id: number
  shop_id: number
  data_identity: string
  channel: string
  status: string
  version: number
  content: FeeRuleContent | null
  created_at: string
  history: FeeRuleHistory[]
}

interface FeeMapping {
  statement_id: number
  status: string
  category?: string | null
  rule_id?: number | null
  rule_version?: number | null
}

interface FeeRuleChange {
  statement_id: number
  fee_name: string
  before: FeeMapping
  after: FeeMapping
}

interface FeeRulePreview {
  preview_hash: string
  source_revision: number
  calculated_at: string
  previous: FeeRuleContent | null
  proposed: FeeRuleContent
  changes: FeeRuleChange[]
  statement_count: number
}

interface ExpenseForm {
  label: string
  category: string
  amount: string
  currency: string
  occurredDay: string
  occurredClock: string
  timezone: string
  evidenceRef: string
  evidenceNote: string
  reason: string
  allocation: string
  orderLineId: number | null
  sourceRowId: number | null
  sourceRevision: number | null
  confirmed: boolean
}

function emptyForm(): ExpenseForm {
  return {
    label: '',
    category: 'shipping',
    amount: '',
    currency: 'USD',
    occurredDay: '',
    occurredClock: '12:00',
    timezone: shopTimezone(),
    evidenceRef: '',
    evidenceNote: '',
    reason: '',
    allocation: 'shop',
    orderLineId: null,
    sourceRowId: null,
    sourceRevision: null,
    confirmed: false,
  }
}

const identity = ref('user_import')
const channel = ref('generic')
const startDay = ref('')
const startClock = ref('00:00')
const endDay = ref('')
const endClock = ref('23:59')
const records = ref<ExpenseSaved[]>([])
const nextCursor = ref<number | null>(null)
const summary = ref<ExpenseSummary | null>(null)
const record = ref<ExpenseSaved | null>(null)
const editing = ref(false)
const form = ref<ExpenseForm>(emptyForm())
const pending = ref(false)
const pendingKey = ref<string | null>(null)
const orderQuery = ref('')
const orders = ref<ExpenseOrder[]>([])
const ordersRevision = ref<number | null>(null)
const rulesVisible = ref(false)
const rules = ref<FeeRuleSaved[]>([])
const ruleRecord = ref<FeeRuleSaved | null>(null)
const ruleForm = ref<{ feeName: string; category: string; reason: string }>({ feeName: '', category: 'other', reason: '' })
const rulePreview = ref<FeeRulePreview | null>(null)
const ruleConfirmed = ref(false)
const pendingRule = ref(false)
const pendingRuleKey = ref<string | null>(null)
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
const categoryOptions = computed(() => Object.entries(expenseCategories).map(([key, label]) => ({ key, label })))
const categoryIndex = computed(() => Math.max(0, Object.keys(expenseCategories).indexOf(form.value.category)))
const ruleCategoryIndex = computed(() => Math.max(0, Object.keys(expenseCategories).indexOf(ruleForm.value.category)))
const allocationIndex = computed(() => Math.max(0, allocationOptions.findIndex((item) => item.key === form.value.allocation)))

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

/** 期间范围：开始/结束均为业务时区下的明确时刻。 */
function scopePayload(): { data_identity: string; channel: string; start_at: string; end_at: string; timezone: string } {
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

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  const today = todayInZone(zone.value)
  if (endDay.value === '' && today !== null) endDay.value = today
  if (startDay.value === '' && today !== null) startDay.value = today
  if (form.value.label === '') form.value = { ...emptyForm(), currency: state.shops.find((shop) => shop.id === state.shopId)?.currency ?? 'USD' }
  await load()
})

async function load(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    const scope = scopePayload()
    const page = asObject<{ items: ExpenseSaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/expenses'), {
        data_identity: scope.data_identity,
        channel: scope.channel,
      }),
    )
    records.value = asRows<ExpenseSaved>(page?.items)
    nextCursor.value = page?.next_cursor ?? null
  })
  error.value = message
}

async function loadMore(): Promise<void> {
  const cursor = nextCursor.value
  if (cursor === null) return
  const message = await perform(async () => {
    const page = asObject<{ items: ExpenseSaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/expenses'), {
        data_identity: identity.value,
        channel: channel.value,
        before: cursor,
      }),
    )
    const incoming = asRows<ExpenseSaved>(page?.items)
    records.value = [
      ...records.value,
      ...incoming.filter((item) => !records.value.some((old) => old.id === item.id)),
    ]
    nextCursor.value = page?.next_cursor ?? null
  })
  error.value = message
}

async function loadSummary(): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<ExpenseSummary>(await apiPost(shopPath('/expenses/summary'), scopePayload()))
    if (value === null) throw new Error('汇总响应无法读取，请刷新重试。')
    summary.value = value
  })
  error.value = message
}

function startCreate(): void {
  record.value = null
  form.value = {
    ...emptyForm(),
    occurredDay: todayInZone(zone.value) ?? '',
    currency: state.shops.find((shop) => shop.id === state.shopId)?.currency ?? 'USD',
  }
  orders.value = []
  ordersRevision.value = null
  orderQuery.value = ''
  pending.value = false
  pendingKey.value = null
  editing.value = true
}

function closeEdit(): void {
  editing.value = false
  record.value = null
  pending.value = false
  pendingKey.value = null
}

function setAllocation(event: unknown): void {
  form.value.allocation = allocationOptions[Number(pickerValue(event))]?.key ?? 'shop'
  if (form.value.allocation === 'shop') {
    form.value.orderLineId = null
    form.value.sourceRowId = null
    form.value.sourceRevision = null
  }
}

function toggleConfirmed(): void {
  if (pending.value) return
  form.value.confirmed = !form.value.confirmed
}

async function openRecord(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<ExpenseSaved>(await apiGet(shopPath(`/expenses/${id}`)))
    if (value === null) throw new Error('费用响应无法读取，请刷新重试。')
    record.value = value
    editing.value = true
    pending.value = false
    pendingKey.value = null
    const content = value.snapshot?.content
    if (content) {
      form.value = {
        label: content.label,
        category: content.category,
        amount: `${content.amount}`,
        currency: content.currency,
        occurredDay: content.occurred_at.slice(0, 10),
        occurredClock: content.occurred_at.slice(11, 16),
        timezone: content.timezone,
        evidenceRef: content.evidence_ref,
        evidenceNote: content.evidence_note,
        reason: content.reason,
        allocation: content.allocation,
        orderLineId: content.order_line_id ?? null,
        sourceRowId: content.expected_source_row_id ?? null,
        sourceRevision: content.expected_source_revision ?? null,
        confirmed: false,
      }
    }
    success('费用记录已回读。')
  })
  error.value = message
}

async function queryOrders(): Promise<void> {
  const message = await perform(async () => {
    if (orderQuery.value.trim() === '') throw new Error('请输入订单号后再查询。')
    const value = asObject<{ source_revision: number; items: ExpenseOrder[] }>(
      await apiGet(shopPath('/expenses/orders'), {
        data_identity: identity.value,
        channel: channel.value,
        order_id: orderQuery.value.trim(),
      }),
    )
    orders.value = asRows<ExpenseOrder>(value?.items)
    ordersRevision.value = value?.source_revision ?? null
    form.value.orderLineId = null
    form.value.sourceRowId = null
  })
  error.value = message
}

function chooseOrder(order: ExpenseOrder): void {
  form.value.orderLineId = order.id
  form.value.sourceRowId = order.source.row_id
  form.value.sourceRevision = ordersRevision.value
}

function amountIsPositive(value: string): boolean {
  if (!isDecimalInput(value) || value.startsWith('-')) return false
  return /[1-9]/.test(value)
}

async function saveRecord(): Promise<void> {
  if (pending.value && record.value !== null) {
    await openRecord(record.value.id)
    return
  }
  const current = record.value
  const key = pendingKey.value ?? newRequestId()
  pendingKey.value = key
  const message = await perform(async () => {
    if (form.value.label.trim() === '') throw new Error('请填写费用名称。')
    if (!amountIsPositive(form.value.amount)) throw new Error('费用金额须为大于 0 的十进制数字。')
    if (form.value.currency.trim() === '') throw new Error('请填写币种。')
    if (!isValidDate(form.value.occurredDay)) throw new Error('请选择合法的发生日期。')
    const occurredAt = zonedIsoFromParts(form.value.occurredDay, form.value.occurredClock, form.value.timezone.trim() === '' ? zone.value : form.value.timezone.trim())
    if (occurredAt === null) throw new Error('发生时间无法换算，请核对发生时区。')
    if (form.value.evidenceRef.trim() === '') throw new Error('请填写凭据唯一编号。')
    if (form.value.evidenceNote.trim() === '') throw new Error('请填写凭据内容与核查依据。')
    if (form.value.reason.trim() === '') throw new Error('请填写录入或修订原因。')
    if (form.value.allocation === 'order_line') {
      if (form.value.orderLineId === null || form.value.sourceRowId === null) {
        throw new Error('请查询并重新选择当前订单行。')
      }
    }
    const content: ExpenseContent = {
      label: form.value.label.trim(),
      category: form.value.category,
      amount: form.value.amount.trim(),
      currency: form.value.currency.trim().toUpperCase(),
      occurred_at: occurredAt,
      timezone: form.value.timezone.trim() === '' ? zone.value : form.value.timezone.trim(),
      evidence_ref: form.value.evidenceRef.trim(),
      evidence_note: form.value.evidenceNote.trim(),
      allocation: form.value.allocation,
      reason: form.value.reason.trim(),
    }
    if (form.value.allocation === 'order_line') {
      content.order_line_id = form.value.orderLineId
      content.expected_source_row_id = form.value.sourceRowId
      content.expected_source_revision = form.value.sourceRevision
    }
    const body = {
      request_id: key,
      confirm: true,
      data_identity: identity.value,
      channel: channel.value,
      version: current?.version ?? 0,
      content,
    }
    const value = asObject<ExpenseSaved>(
      await apiPost(current === null ? shopPath('/expenses') : shopPath(`/expenses/${current.id}`), body),
    )
    if (value === null) throw new Error('保存响应无法读取，请到费用列表回读核对。')
    pending.value = false
    pendingKey.value = null
    record.value = value
    await load()
  })
  if (message === '') success('费用版本已保存，请与账单核对后再确认口径。')
  else {
    pending.value = true
    error.value = message
  }
}

async function controlRecord(action: 'withdraw' | 'clear'): Promise<void> {
  const current = record.value
  if (current === null) return
  const modal = await Taro.showModal({
    title: action === 'clear' ? '清除费用正文' : '撤销费用',
    content: action === 'clear' ? '清除该费用及版本历史中的正文，无法恢复。' : '撤销当前费用；历史仍可回读。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<ExpenseSaved>(
      await apiPost(shopPath(`/expenses/${current.id}/${action}`), {
        request_id: newRequestId(),
        version: current.version,
        confirm: true,
      }),
    )
    if (value !== null) record.value = value
    await load()
  }, '费用状态已更新。', '费用详情')
}

async function loadRules(): Promise<void> {
  const message = await perform(async () => {
    const scope = scopePayload()
    const page = asObject<{ items: FeeRuleSaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/fee-rules'), {
        data_identity: scope.data_identity,
        channel: scope.channel,
      }),
    )
    rules.value = asRows<FeeRuleSaved>(page?.items)
    rulesVisible.value = true
  })
  error.value = message
}

function resetRuleDraft(): void {
  ruleRecord.value = null
  rulePreview.value = null
  ruleConfirmed.value = false
  pendingRule.value = false
  pendingRuleKey.value = null
  ruleForm.value = { feeName: '', category: 'other', reason: '' }
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

async function openRule(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<FeeRuleSaved>(await apiGet(shopPath(`/fee-rules/${id}`)))
    if (value === null) throw new Error('规则响应无法读取，请刷新重试。')
    ruleRecord.value = value
    rulePreview.value = null
    ruleConfirmed.value = false
    pendingRule.value = false
    pendingRuleKey.value = null
    ruleForm.value = {
      feeName: value.content?.fee_name ?? '',
      category: value.content?.category ?? 'other',
      reason: value.content?.reason ?? '',
    }
    success('费用映射记录已回读。')
  })
  error.value = message
}

async function previewRule(): Promise<void> {
  const message = await perform(async () => {
    if (ruleForm.value.feeName.trim() === '') throw new Error('请填写账单费用名称。')
    if (ruleForm.value.reason.trim() === '') throw new Error('请填写分类与修订依据。')
    const value = asObject<FeeRulePreview>(
      await apiPost(shopPath('/fee-rules/preview'), {
        scope: scopePayload(),
        rule_id: ruleRecord.value?.id ?? null,
        version: ruleRecord.value?.version ?? 0,
        content: {
          fee_name: ruleForm.value.feeName.trim(),
          category: ruleForm.value.category,
          reason: ruleForm.value.reason.trim(),
        },
      }),
    )
    if (value === null) throw new Error('预览响应无法读取，请刷新后重试。')
    rulePreview.value = value
    ruleConfirmed.value = false
  })
  error.value = message
}

async function saveRule(): Promise<void> {
  const preview = rulePreview.value
  if (preview === null) return
  if (pendingRule.value && ruleRecord.value !== null) {
    await openRule(ruleRecord.value.id)
    return
  }
  const key = pendingRuleKey.value ?? newRequestId()
  pendingRuleKey.value = key
  await writeAction(async () => {
    const value = asObject<FeeRuleSaved>(
      await apiPost(shopPath('/fee-rules'), {
        scope: scopePayload(),
        rule_id: ruleRecord.value?.id ?? null,
        version: ruleRecord.value?.version ?? 0,
        content: preview.proposed,
        preview_hash: preview.preview_hash,
        request_id: key,
        confirm: true,
      }),
    )
    if (value === null) throw new Error('保存响应无法读取，请到规则列表回读核对。')
    pendingRule.value = false
    pendingRuleKey.value = null
    ruleRecord.value = value
    rulePreview.value = null
    ruleConfirmed.value = false
    await loadRules()
  }, '费用映射规则已保存；账单分类须按当前规则重新核对。', '规则列表')
}

async function controlRule(action: 'withdraw' | 'clear'): Promise<void> {
  const current = ruleRecord.value
  if (current === null) return
  const modal = await Taro.showModal({
    title: action === 'clear' ? '清除映射正文' : '撤销映射规则',
    content: action === 'clear' ? '清除规则及历史正文，无法恢复。' : '撤销该规则后，账单分类须按当前规则重新核对。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<FeeRuleSaved>(
      await apiPost(shopPath(`/fee-rules/${current.id}/${action}`), {
        request_id: newRequestId(),
        version: current.version,
        confirm: true,
      }),
    )
    if (value !== null) ruleRecord.value = value
    await loadRules()
  }, '规则状态已更新。', '规则列表')
}
</script>
