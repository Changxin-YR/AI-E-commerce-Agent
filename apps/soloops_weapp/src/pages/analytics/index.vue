<template>
  <PageShell
    title="经营分析"
    subtitle="按单店、单币种与明确时间窗计算；未知值和缺失费用单独保留。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <FactLine label="所属店铺" :value="shopName" />
    <FactLine label="业务时区" :value="zone" />

    <text class="section-title">分析范围</text>
    <view class="field">
      <text class="field__label">采购成本口径</text>
      <picker mode="selector" :range="costModeOptions" range-key="label" :value="costModeIndex" @change="setCostMode($event)">
        <view class="field__picker">{{ labelOf(costModes, costMode) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">分析范围</text>
      <picker mode="selector" :range="intentOptions" range-key="label" :value="intentIndex" @change="setIntent($event)">
        <view class="field__picker">{{ labelOf(intents, intent) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">数据身份</text>
      <picker mode="selector" :range="identityOptions" range-key="label" :value="identityIndex" @change="identity = identityOptions[Number(pickerValue($event))]?.key ?? 'user_import'">
        <view class="field__picker">{{ labelOf(importIdentities, identity) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">来源渠道（可留空表示不限）</text>
      <picker mode="selector" :range="channelOptions" range-key="label" :value="channelIndex" @change="channel = channelOptions[Number(pickerValue($event))]?.key ?? ''">
        <view class="field__picker">{{ channel === '' ? '不限渠道' : labelOf(importChannels, channel) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">开始日期</text>
      <picker mode="date" :value="startDay" @change="startDay = pickerValue($event)">
        <view class="field__picker">{{ startDay === '' ? '请选择开始日期' : startDay }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">开始时间（业务时区）</text>
      <picker mode="time" :value="startClock" @change="startClock = pickerValue($event)">
        <view class="field__picker">{{ startClock === '' ? '请选择开始时间' : startClock }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">结束日期（区间为 [开始, 结束)）</text>
      <picker mode="date" :value="endDay" @change="endDay = pickerValue($event)">
        <view class="field__picker">{{ endDay === '' ? '请选择结束日期' : endDay }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">结束时间（业务时区）</text>
      <picker mode="time" :value="endClock" @change="endClock = pickerValue($event)">
        <view class="field__picker">{{ endClock === '' ? '请选择结束时间' : endClock }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">币种</text>
      <input class="field__input" :value="currency" :disabled="busy" @input="currency = inputValue($event).toUpperCase()" />
    </view>
    <view class="field">
      <text class="field__label">最小购买数量</text>
      <input class="field__input" type="number" :value="minQuantity" :disabled="busy" @input="minQuantity = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">低毛利上限（百分比）</text>
      <input class="field__input" :value="maxMarginPercent" :disabled="busy" @input="maxMarginPercent = inputValue($event)" />
    </view>

    <view class="row">
      <ActionButton label="按范围计算" variant="primary" :disabled="busy" @tap="calculate(false)" />
      <ActionButton label="导入订单与成本来源" :disabled="busy" @tap="openPage('/pages/imports/index', { kind: 'orders' })" />
    </view>

    <text class="section-title">受控经营问答</text>
    <text class="hint">
      本地规则只支持销售汇总、购买数量前五与已知毛利筛选；超出范围的问题会被明确拒绝，不猜测答案。
    </text>
    <view class="field">
      <text class="field__label">受控经营问题（1–200 字）</text>
      <input class="field__input" :value="question" :disabled="busy" @input="question = inputValue($event)" />
    </view>
    <view class="row">
      <ActionButton label="用本地规则回答" :disabled="busy" @tap="calculate(true)" />
      <ActionButton label="进入 AI 经营问数并核对预算" :disabled="busy" @tap="openPage('/pages/agent/index', { template: 'analysis' })" />
    </view>

    <template v-if="result">
      <text class="section-title">分析结果</text>
      <text v-if="outdated" class="warn">来源或历史成本依据已变化，请重新计算后保存新的报告。</text>
      <FactLine label="结果范围" :value="`${result.scope.start_at} 至 ${result.scope.end_at} · ${result.scope.timezone}`" :zone="zone" />
      <FactLine label="来源版本 / 计算版本 / 计算时间" :value="`${result.source_revision} / ${result.calculation_version ?? '未知'} / ${businessTimeText(result.calculated_at, zone)}`" />
      <FactLine label="计算引擎" :value="result.engine" />
      <FactLine label="成本口径" :value="result.cost_basis" />
      <FactLine label="公式" :value="result.formula" />
      <FactLine
        label="费用缺口"
        :value="(result.fee_gaps ?? []).length === 0 ? '服务端未返回缺口项' : (result.fee_gaps ?? []).join(' / ')"
      />
      <text v-for="warning in result.warnings ?? []" :key="warning" class="warn">{{ warning }}</text>
      <text v-if="result.answer" class="card__title">回答</text>
      <text v-if="result.answer" class="hint">{{ result.answer }}</text>
      <text v-if="(result.candidates ?? []).length > 0" class="hint">
        候选追问：{{ (result.candidates ?? []).join(' / ') }}
      </text>
      <text v-if="result.ranking_available !== true" class="warn">
        当前范围排名不可用（可能是有效订单不足或缺少已知成本），不展示排行结论。
      </text>

      <text class="section-title">汇总</text>
      <view class="card">
        <text class="card__title">全部范围</text>
        <text class="hint">{{ summaryText(result.summary) }}</text>
        <FactLine label="销售金额" :value="moneyText(result.summary.sales, currency)" />
        <FactLine label="已确认销售小计 / 已知行数" :value="`${result.summary.known_sales_subtotal} / ${result.summary.sales_known_lines}`" />
        <FactLine label="成本 / 已知成本小计 / 已知行数" :value="`${moneyText(result.summary.cost, currency)} / ${result.summary.known_cost_subtotal} / ${result.summary.cost_known_lines}`" />
        <FactLine label="毛利 / 已知毛利小计 / 已知行数" :value="`${moneyText(result.summary.gross_profit, currency)} / ${result.summary.known_gross_subtotal} / ${result.summary.gross_known_lines}`" />
        <FactLine label="毛利率" :value="result.summary.margin_percent === null || result.summary.margin_percent === undefined ? '未知' : `${result.summary.margin_percent}%`" />
      </view>
      <view v-for="item in result.skus ?? []" :key="item.sku ?? 'unknown'" class="card">
        <text class="card__title">SKU {{ item.sku ?? '未知' }}</text>
        <text class="hint">{{ summaryText(item) }}</text>
        <FactLine label="销售 / 成本 / 毛利" :value="`${moneyText(item.sales, currency)} / ${moneyText(item.cost, currency)} / ${moneyText(item.gross_profit, currency)}`" />
      </view>

      <text class="section-title">订单行与来源</text>
      <text class="hint">每页 50 行。缺成本的行保留在结果中，缺口单列，不按 0 计入。</text>
      <view v-for="line in pagedLines" :key="`${line.order_id}:${line.line_id}`" class="card">
        <text class="card__title">{{ line.order_id }} / {{ line.line_id }} · {{ line.sku }}</text>
        <text class="hint">{{ line.status }} · {{ businessTimeText(line.ordered_at, zone) }} · 数量 {{ line.quantity }} · {{ line.included ? '已纳入统计' : '未纳入统计' }}</text>
        <FactLine label="单价 / 折扣 / 退款" :value="`${moneyText(line.unit_price, line.currency)} / ${moneyText(line.discount, line.currency)} / ${moneyText(line.refund, line.currency)}`" />
        <FactLine label="销售 / 成本 / 毛利" :value="`${moneyText(line.sales, line.currency)} / ${moneyText(line.cost, line.currency)} / ${moneyText(line.gross_profit, line.currency)}`" />
        <FactLine label="单位成本（当前口径）" :value="moneyText(line.unit_cost, line.currency)" />
        <FactLine
          label="历史成本"
          :value="line.historical_cost ? `${moneyText(line.historical_cost.unit_cost, line.historical_cost.currency)} · 版本 ${line.historical_cost.version} · ${line.historical_cost.status}` : '未知'"
        />
        <FactLine label="缺口" :value="(line.gaps ?? []).length === 0 ? '无' : (line.gaps ?? []).join(' / ')" />
        <FactLine label="来源" :value="`${line.source.filename} · 第 ${line.source.row_number} 行 · 批次 ${line.source.batch_id}`" />
        <view class="row">
          <ActionButton label="登记 / 修订历史成本" :disabled="busy" @tap="openCost(line.source.row_id)" />
          <ActionButton label="查看来源原文" :disabled="busy" @tap="openSource(line.source.row_id)" />
        </view>
      </view>
      <view v-if="(result.lines ?? []).length > 0" class="row">
        <ActionButton label="上 50 行" :disabled="busy || linePage === 0" @tap="linePage -= 1" />
        <text class="chip">第 {{ linePage + 1 }} / {{ linePages }} 页</text>
        <ActionButton label="下 50 行" :disabled="busy || linePage + 1 >= linePages" @tap="linePage += 1" />
      </view>
      <view v-if="(result.lines ?? []).length === 0" class="card">
        <text class="hint">当前范围没有订单行。请调整范围或先导入订单与成本来源。</text>
      </view>

      <ActionButton label="保存当前分析报告" variant="primary" block :disabled="busy" @tap="saveReport" />
    </template>

    <template v-if="costDetail">
      <text class="section-title">订单行历史成本</text>
      <FactLine label="订单 / 行 / SKU" :value="`${costDetail.order_id} / ${costDetail.line_id} / ${costDetail.sku}`" />
      <FactLine label="来源批次 / 行 / 修订号" :value="`${costDetail.source_batch_id} / ${costDetail.source_row_id} / ${costDetail.source_revision}`" />
      <FactLine label="渠道 / 数据身份" :value="`${costDetail.channel} / ${costDetail.data_identity}`" />
      <FactLine label="当前来源有效" :value="costDetail.source_current" />
      <FactLine label="当前版本" :value="costDetail.version" />
      <text class="hint">此成本是卖家提供的订单行历史单位采购成本；凭据变更后需重新计算。</text>
      <view class="field">
        <text class="field__label">单位采购成本（最多 4 位小数）</text>
        <input class="field__input" :value="costUnit" :disabled="busy" @input="costUnit = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">币种</text>
        <input class="field__input" :value="costCurrency" :disabled="busy" @input="costCurrency = inputValue($event).toUpperCase()" />
      </view>
      <view class="field">
        <text class="field__label">凭据索引</text>
        <input class="field__input" :value="costEvidence" :disabled="busy" @input="costEvidence = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">凭据时间</text>
        <picker mode="date" :value="costEvidenceDay" @change="costEvidenceDay = pickerValue($event)">
          <view class="field__picker">{{ costEvidenceDay === '' ? '请选择凭据日期' : costEvidenceDay }}</view>
        </picker>
      </view>
      <view class="card" @tap="costConfirmed = !costConfirmed">
        <text class="chip" :class="{ 'chip--active': costConfirmed }">
          {{ costConfirmed ? '已确认' : '未确认' }} · 确认这是卖家提供的订单行历史单位采购成本依据
        </text>
      </view>
      <view class="row">
        <ActionButton label="保存成本新版本" variant="primary" :disabled="busy || !costConfirmed" @tap="writeCost('upsert')" />
        <ActionButton label="撤销当前凭据" :disabled="busy" @tap="writeCost('revoke')" />
        <ActionButton label="回读版本与来源" :disabled="busy" @tap="openCost(costDetail.source_row_id)" />
        <ActionButton label="关闭成本面板" :disabled="busy" @tap="costDetail = null" />
      </view>
      <text v-if="costMessage" class="hint">{{ costMessage }}</text>
      <text class="section-title">成本版本历史</text>
      <view v-for="version in costDetail.history ?? []" :key="version.id" class="card">
        <text class="card__title">版本 {{ version.version }} · {{ version.action }} · {{ version.status }}</text>
        <FactLine label="单位成本 / 币种" :value="moneyText(version.unit_cost, version.currency)" />
        <FactLine label="凭据索引" :value="version.evidence_ref" />
        <FactLine label="凭据时间" :value="version.evidence_at" :zone="zone" />
        <FactLine label="登记时间" :value="version.recorded_at" :zone="zone" />
      </view>
    </template>

    <template v-if="source">
      <text class="section-title">来源原文与转换结果</text>
      <FactLine label="来源" :value="`${source.reference.filename} · 第 ${source.reference.row_number} 行 · 批次 ${source.reference.batch_id}（${source.batch_status}）`" />
      <FactLine label="导入时间 / 导出时间" :value="`${businessTimeText(source.reference.imported_at, zone)} / ${factText(source.reference.exported_at)}`" />
      <view v-for="(value, key) in source.raw" :key="`raw:${key}`">
        <FactLine :label="`原始 ${key}`" :value="value" />
      </view>
      <view v-for="(value, key) in source.corrections" :key="`fix:${key}`">
        <FactLine :label="`修正 ${key}`" :value="value" />
      </view>
      <view v-for="(value, key) in source.normalized" :key="`norm:${key}`">
        <FactLine :label="`转换后 ${key}`" :value="value" />
      </view>
      <ActionButton label="关闭来源面板" :disabled="busy" @tap="source = null" />
    </template>

    <text class="section-title">报告历史</text>
    <view class="row">
      <ActionButton label="刷新报告与来源状态" :disabled="busy" @tap="load" />
    </view>
    <view v-if="history.length === 0 && !busy" class="card">
      <text class="hint">暂无已保存分析。先按范围计算，再保存报告。</text>
    </view>
    <view v-for="item in history" :key="item.id" class="card">
      <text class="card__title">报告 #{{ item.id }} · {{ item.scope.currency }} · {{ item.status }}</text>
      <text class="hint">{{ businessTimeText(item.created_at, zone) }} · 来源版本 {{ item.source_revision }}</text>
      <text class="hint">{{ item.scope.start_at }} 至 {{ item.scope.end_at }}</text>
      <FactLine v-if="item.todo" label="核对待办" :value="`#${item.todo.id} · ${item.todo.title} · ${item.todo.status}`" />
      <view class="row">
        <ActionButton label="回读报告" :disabled="busy" @tap="inspect(item.id)" />
        <ActionButton label="按此报告范围重新计算" :disabled="busy" @tap="reuseScope(item)" />
        <ActionButton v-if="item.todo" :label="item.todo.status === 'completed' ? '重开核对待办' : '标记核对完成'" :disabled="busy" @tap="todoAction(item, item.todo.status === 'completed' ? 'reopen' : 'complete')" />
        <ActionButton v-else label="创建关联核对待办" :disabled="busy" @tap="todoAction(item, 'create')" />
        <ActionButton label="返回来源待办" :disabled="busy" @tap="openPage('/pages/tasks/index')" />
      </view>
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 经营分析：范围计算、受控问答、订单行历史成本、来源核对与持久报告。
 * 接口（均来自 contracts/ui-contract.json 的 r2.analytics）：
 *   POST /api/shops/{shop_id}/analytics/calculate
 *   POST /api/shops/{shop_id}/analytics/ask
 *   GET  /api/shops/{shop_id}/analytics/revision
 *   GET  /api/shops/{shop_id}/analytics/saved
 *   POST /api/shops/{shop_id}/analytics/saved
 *   GET  /api/shops/{shop_id}/analytics/saved/{analysis_id}
 *   POST /api/shops/{shop_id}/analytics/saved/{analysis_id}/todo
 *   POST /api/shops/{shop_id}/analytics/saved/{analysis_id}/todo/action
 *   GET  /api/shops/{shop_id}/analytics/order-costs/{row_id}
 *   POST /api/shops/{shop_id}/analytics/order-costs/{row_id}
 *   GET  /api/shops/{shop_id}/analytics/sources/{row_id}
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import ActionButton from '../../ui/ActionButton.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import { ApiError, apiGet, apiPost, asObject, asRows, newRequestId } from '../../core/api'
import { businessTimeText, factText, isValidDate, isDecimalInput, moneyText, todayInZone, zonedIsoFromParts } from '../../core/format'
import { importChannels, importIdentities, labelOf } from '../../core/labels'
import { openPage } from '../../core/links'
import { ensureSession, perform, shopPath, shopCurrency, shopTimezone, state } from '../../core/store'

interface AnalysisScope {
  cost_mode: string
  start_at: string
  end_at: string
  timezone: string
  currency: string
  data_identity: string
  channel?: string | null
  intent: string
  min_quantity: number
  max_margin_percent: string
}

interface MetricSummary {
  sku?: string | null
  line_count: number
  purchased_quantity: number
  sales?: string | null
  known_sales_subtotal: string
  sales_known_lines: number
  cost?: string | null
  known_cost_subtotal: string
  cost_known_lines: number
  gross_profit?: string | null
  known_gross_subtotal: string
  gross_known_lines: number
  margin_percent?: string | null
}

interface SourceReference {
  origin?: string
  batch_id: number
  row_id: number
  row_number: number
  filename: string
  sheet_name: string
  exported_at?: string | null
  imported_at: string
  data_identity: string
}

interface CostVersion {
  id: number
  version: number
  action: string
  status: string
  unit_cost?: string | null
  currency?: string | null
  evidence_ref?: string | null
  evidence_at?: string | null
  recorded_at: string
}

interface CostHistory {
  source_row_id: number
  source_batch_id: number
  source_current: boolean
  source_revision: number
  order_id: string
  line_id: string
  sku: string
  currency: string
  channel: string
  data_identity: string
  version: number
  history: CostVersion[]
}

interface LineResult {
  unit_cost?: string | null
  historical_cost?: CostVersion | null
  order_id: string
  line_id: string
  sku: string
  status: string
  ordered_at: string
  currency: string
  quantity: number
  included: boolean
  unit_price: string
  discount?: string | null
  refund?: string | null
  sales?: string | null
  cost?: string | null
  gross_profit?: string | null
  gaps: string[]
  source: SourceReference
  cost_source?: SourceReference | null
}

interface AnalysisResult {
  calculation_version?: number
  scope: AnalysisScope
  source_revision: number
  calculated_at: string
  engine?: string
  formula: string
  cost_basis: string
  fee_gaps: string[]
  warnings: string[]
  summary: MetricSummary
  skus: MetricSummary[]
  lines: LineResult[]
  ranking_available: boolean
  answer: string
  candidates: string[]
}

interface TodoOutput {
  id: number
  title: string
  status: string
  version: number
}

interface SavedOutput {
  id: number
  shop_id: number
  source_revision: number
  status: string
  created_at: string
  scope: AnalysisScope
  snapshot: AnalysisResult | null
  todo: TodoOutput | null
}

interface SourceOutput {
  reference: SourceReference
  batch_status: string
  raw: Record<string, unknown>
  corrections: Record<string, unknown>
  normalized: Record<string, unknown>
}

const costModes: Record<string, string> = {
  current_estimate: '当前商品成本回推估算',
  seller_history: '订单行历史成本依据',
}

const intents: Record<string, string> = {
  summary: '销售与已知毛利汇总',
  sales: '购买数量前五 SKU',
  low_margin: '低毛利筛选',
}

const costMode = ref('current_estimate')
const intent = ref('summary')
const identity = ref('user_import')
const channel = ref('')
const startDay = ref('')
const startClock = ref('00:00')
const endDay = ref('')
const endClock = ref('23:59')
const currency = ref('')
const minQuantity = ref('1')
const maxMarginPercent = ref('20')
const question = ref('查看销售与已知毛利')
const result = ref<AnalysisResult | null>(null)
const history = ref<SavedOutput[]>([])
const selected = ref<SavedOutput | null>(null)
const outdated = ref(false)
const linePage = ref(0)
const costDetail = ref<CostHistory | null>(null)
const costUnit = ref('')
const costCurrency = ref('')
const costEvidence = ref('')
const costEvidenceDay = ref('')
const costConfirmed = ref(false)
const costMessage = ref('')
const source = ref<SourceOutput | null>(null)
const busy = ref(false)
const error = ref('')
const successText = ref('')
const ready = ref(false)

const zone = computed(() => shopTimezone())
const shopName = computed(() => state.shops.find((shop) => shop.id === state.shopId)?.name ?? '未知')
const costModeOptions = computed(() => optionsOf(costModes))
const intentOptions = computed(() => optionsOf(intents))
const identityOptions = computed(() => optionsOf(importIdentities))
const channelOptions = computed(() => [{ key: '', label: '不限渠道' }, ...optionsOf(importChannels)])
const costModeIndex = computed(() => indexOf(costModes, costMode.value))
const intentIndex = computed(() => indexOf(intents, intent.value))
const identityIndex = computed(() => indexOf(importIdentities, identity.value))
const channelIndex = computed(() => channelOptions.value.findIndex((item) => item.key === channel.value))
const lines = computed(() => result.value?.lines ?? [])
const linePages = computed(() => Math.max(1, Math.ceil(lines.value.length / 50)))
const pagedLines = computed(() => lines.value.slice(linePage.value * 50, linePage.value * 50 + 50))

function optionsOf(map: Record<string, string>): Array<{ key: string; label: string }> {
  return Object.entries(map).map(([key, label]) => ({ key, label }))
}

function indexOf(map: Record<string, string>, key: string): number {
  const index = Object.keys(map).indexOf(key)
  return index < 0 ? 0 : index
}

function setCostMode(event: unknown): void {
  costMode.value = costModeOptions.value[Number(pickerValue(event))]?.key ?? 'current_estimate'
}

function setIntent(event: unknown): void {
  intent.value = intentOptions.value[Number(pickerValue(event))]?.key ?? 'summary'
}

/** 汇总一句话：全部数字来自服务端字符串，不做本地汇总。 */
function summaryText(item: MetricSummary): string {
  return `行数 ${item.line_count} · 购买数量 ${item.purchased_quantity} · 已知销售 ${item.sales_known_lines} 行 · 已知成本 ${item.cost_known_lines} 行 · 已知毛利 ${item.gross_known_lines} 行`
}

function success(text: string): void {
  successText.value = text
  void Taro.showToast({ title: text, icon: 'none' })
}

/**
 * 写操作统一包装：成功提示回读口径；断线/超时提示“结果未知，请回读”，
 * 不得由 HTTP 200 或超时推断成功。
 */
async function writeAction(
  action: () => Promise<void>,
  done: string,
  hint: string,
): Promise<void> {
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

function scopePayload(): AnalysisScope {
  if (!isValidDate(startDay.value) || !isValidDate(endDay.value)) {
    throw new Error('请选择合法的开始与结束日期。')
  }
  const start = zonedIsoFromParts(startDay.value, startClock.value, zone.value)
  const end = zonedIsoFromParts(endDay.value, endClock.value, zone.value)
  if (start === null || end === null) {
    throw new Error('业务时间无法换算，请核对时区与时间（例如夏令时跳变）。')
  }
  if (currency.value.trim() === '') throw new Error('请填写币种，例如 USD。')
  if (!/^\d+$/.test(minQuantity.value.trim())) throw new Error('最小购买数量须为不小于 1 的整数。')
  if (!isDecimalInput(maxMarginPercent.value)) throw new Error('低毛利上限须为数字百分比。')
  return {
    cost_mode: costMode.value,
    start_at: start,
    end_at: end,
    timezone: zone.value,
    currency: currency.value.trim().toUpperCase(),
    data_identity: identity.value,
    channel: channel.value === '' ? null : channel.value,
    intent: intent.value,
    min_quantity: Number(minQuantity.value.trim()),
    max_margin_percent: maxMarginPercent.value.trim(),
  }
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  const today = todayInZone(zone.value)
  if (startDay.value === '' && today !== null) {
    startDay.value = today
    endDay.value = today
  }
  if (currency.value === '') currency.value = shopCurrency()
  await load()
})

async function load(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    history.value = asRows<SavedOutput>(await apiGet(shopPath('/analytics/saved')))
    if (result.value !== null) {
      const revision = await apiGet<number>(shopPath('/analytics/revision'))
      if (`${revision}` !== `${result.value.source_revision}`) outdated.value = true
    }
  })
  error.value = message
}

async function calculate(ask: boolean): Promise<void> {
  const message = await perform(async () => {
    const scope = scopePayload()
    const value = ask
      ? asObject<AnalysisResult>(
          await apiPost(shopPath('/analytics/ask'), { scope, question: question.value.trim() }),
        )
      : asObject<AnalysisResult>(await apiPost(shopPath('/analytics/calculate'), scope))
    if (value === null) throw new Error('分析响应无法读取，请刷新重试。')
    result.value = value
    selected.value = null
    outdated.value = false
    linePage.value = 0
  })
  if (message === '') success(ask ? '已按本地规则回答，请核对依据与缺口。' : '计算完成，请核对来源版本与费用缺口。')
  else error.value = message
}

async function saveReport(): Promise<void> {
  const current = result.value
  if (current === null) return
  const modal = await Taro.showModal({
    title: '保存分析报告',
    content: `按当前来源版本 ${current.source_revision} 保存报告；来源变化后报告会标记为需重算。`,
    confirmText: '保存',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<SavedOutput>(
      await apiPost(shopPath('/analytics/saved'), {
        scope: current.scope,
        expected_revision: current.source_revision,
      }),
    )
    if (value === null) throw new Error('保存响应无法读取，请到报告历史回读核对。')
    selected.value = value
    result.value = value.snapshot
    await load()
  }, '分析报告已保存。', '报告')
}

async function inspect(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<SavedOutput>(await apiGet(shopPath(`/analytics/saved/${id}`)))
    if (value === null) throw new Error('报告响应无法读取，请刷新重试。')
    selected.value = value
    result.value = value.snapshot
    outdated.value = value.status !== 'current'
    linePage.value = 0
    const saved = value.scope
    costMode.value = saved.cost_mode
    intent.value = saved.intent
    identity.value = saved.data_identity
    channel.value = saved.channel ?? ''
    currency.value = saved.currency
    minQuantity.value = `${saved.min_quantity}`
    maxMarginPercent.value = `${saved.max_margin_percent}`
  })
  error.value = message
}

function reuseScope(item: SavedOutput): void {
  const saved = item.scope
  costMode.value = saved.cost_mode
  intent.value = saved.intent
  identity.value = saved.data_identity
  channel.value = saved.channel ?? ''
  currency.value = saved.currency
  minQuantity.value = `${saved.min_quantity}`
  maxMarginPercent.value = `${saved.max_margin_percent}`
  const start = saved.start_at.slice(0, 10)
  const end = saved.end_at.slice(0, 10)
  if (isValidDate(start)) startDay.value = start
  if (isValidDate(end)) endDay.value = end
  startClock.value = saved.start_at.slice(11, 16)
  endClock.value = saved.end_at.slice(11, 16)
  success('已恢复报告范围，请重新计算。')
}

async function todoAction(item: SavedOutput, action: string): Promise<void> {
  await writeAction(async () => {
    const path = action === 'create'
      ? shopPath(`/analytics/saved/${item.id}/todo`)
      : shopPath(`/analytics/saved/${item.id}/todo/action`)
    const body = action === 'create'
      ? undefined
      : { expected_version: item.todo?.version ?? 0, action }
    const value = asObject<SavedOutput>(await apiPost(path, body))
    if (value !== null) selected.value = value
    await load()
  }, '核对待办状态已更新。', '核对待办')
}

async function openCost(rowId: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<CostHistory>(await apiGet(shopPath(`/analytics/order-costs/${rowId}`)))
    if (value === null) throw new Error('历史成本响应无法读取，请刷新重试。')
    costDetail.value = value
    costCurrency.value = value.currency
    const latest = value.history.length > 0 ? value.history[value.history.length - 1] : null
    costUnit.value = latest?.unit_cost ?? ''
    costEvidence.value = latest?.evidence_ref ?? ''
    const day = latest?.evidence_at ? latest.evidence_at.slice(0, 10) : ''
    costEvidenceDay.value = isValidDate(day) ? day : ''
    costConfirmed.value = false
    costMessage.value = ''
  })
  error.value = message
}

async function writeCost(action: 'upsert' | 'revoke'): Promise<void> {
  const current = costDetail.value
  if (current === null) return
  const modal = await Taro.showModal({
    title: action === 'revoke' ? '撤销订单行历史成本' : '保存订单行历史成本',
    content: action === 'revoke'
      ? '当前成本凭据将撤销，版本历史保留，采用该依据的分析需重算。'
      : '保存后采用该依据的分析需重新计算；请确认凭据真实可核。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const body: Record<string, unknown> = {
      request_id: newRequestId(),
      expected_version: current.version,
      expected_revision: current.source_revision,
      action,
    }
    if (action === 'upsert') {
      if (!isDecimalInput(costUnit.value) || Number(costUnit.value) < 0) {
        throw new Error('请填写非负单位成本（最多 4 位小数）、凭据索引，并确认历史成本口径。')
      }
      if (costCurrency.value.trim() === '' || costEvidence.value.trim() === '') {
        throw new Error('请填写币种与凭据索引。')
      }
      if (!isValidDate(costEvidenceDay.value)) throw new Error('请选择凭据日期。')
      if (!costConfirmed.value) throw new Error('请先确认这是卖家提供的订单行历史单位采购成本依据。')
      const evidenceAt = zonedIsoFromParts(costEvidenceDay.value, '00:00', zone.value)
      if (evidenceAt === null) throw new Error('凭据时间无法换算，请核对时区。')
      body.content = {
        unit_cost: costUnit.value.trim(),
        currency: costCurrency.value.trim().toUpperCase(),
        evidence_ref: costEvidence.value.trim(),
        evidence_at: evidenceAt,
        confirmed: true,
      }
    }
    await apiPost(shopPath(`/analytics/order-costs/${current.source_row_id}`), body)
    const value = asObject<CostHistory>(await apiGet(shopPath(`/analytics/order-costs/${current.source_row_id}`)))
    if (value === null) throw new Error('回读失败，请到订单行历史成本核对结果。')
    costDetail.value = value
    costMessage.value = '历史成本依据已更新，返回分析页后请重新计算。'
    await load()
  }, '历史成本依据已更新，返回分析页后请重新计算。', '历史成本')
}

async function openSource(rowId: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<SourceOutput>(await apiGet(shopPath(`/analytics/sources/${rowId}`)))
    if (value === null) throw new Error('来源响应无法读取，请刷新重试。')
    source.value = value
  })
  error.value = message
}
</script>
