<template>
  <PageShell
    title="跨店经营总览"
    subtitle="按业务时区的日历日期统计，结束日不计入。各币种分别汇总，保留未知项。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <text class="section-title">店铺与统计范围</text>
    <text class="hint">选择 1–20 家店铺；不同币种不合并成一个数，未知项单独保留。</text>
    <view class="row">
      <text
        v-for="shop in state.shops"
        :key="shop.id"
        class="chip"
        :class="{ 'chip--active': selectedShops.includes(shop.id) }"
        @tap="toggleShop(shop.id)"
      >
        {{ shop.name }} · {{ shop.platform ?? '未知' }} · {{ shop.market ?? '未知' }}
      </text>
    </view>
    <view v-if="state.shops.length === 0" class="card">
      <text class="hint">账号下暂无店铺。请先创建店铺并导入来源数据。</text>
    </view>

    <view class="field">
      <text class="field__label">数据身份</text>
      <picker mode="selector" :range="identityOptions" range-key="label" :value="identityIndex" @change="identity = identityOptions[Number(pickerValue($event))]?.key ?? 'user_import'">
        <view class="field__picker">{{ labelOf(importIdentities, identity) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">业务时区（IANA）</text>
      <input class="field__input" :value="zone" :disabled="busy" @input="zoneInput = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">开始日期</text>
      <picker mode="date" :value="startDay" @change="startDay = pickerValue($event)">
        <view class="field__picker">{{ startDay === '' ? '请选择开始日期' : startDay }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">结束日期（不含此日）</text>
      <picker mode="date" :value="endDay" @change="endDay = pickerValue($event)">
        <view class="field__picker">{{ endDay === '' ? '请选择结束日期' : endDay }}</view>
      </picker>
    </view>
    <view class="row">
      <ActionButton v-for="quick in quickRanges" :key="quick.days" :label="quick.label" :disabled="busy" @tap="applyQuick(quick.days)" />
    </view>
    <text class="hint">快捷摘要以填写的结束日期为截止日，向前取 1、7 或 30 天。</text>

    <view class="card" @tap="customComparison = !customComparison">
      <text class="chip" :class="{ 'chip--active': customComparison }">
        {{ customComparison ? '已开启' : '未开启' }} · 自选对比区间
      </text>
      <text class="hint">关闭时使用紧邻本期之前的等长区间。</text>
    </view>
    <template v-if="customComparison">
      <view class="field">
        <text class="field__label">对比开始日期</text>
        <picker mode="date" :value="comparisonStart" @change="comparisonStart = pickerValue($event)">
          <view class="field__picker">{{ comparisonStart === '' ? '请选择对比开始日期' : comparisonStart }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">对比结束日期</text>
        <picker mode="date" :value="comparisonEnd" @change="comparisonEnd = pickerValue($event)">
          <view class="field__picker">{{ comparisonEnd === '' ? '请选择对比结束日期' : comparisonEnd }}</view>
        </picker>
      </view>
    </template>

    <text class="section-title">币种（不选则读取数据中的全部币种）</text>
    <view class="row">
      <text
        v-for="item in currencies"
        :key="item"
        class="chip"
        :class="{ 'chip--active': selectedCurrencies.includes(item) }"
        @tap="toggleCurrency(item)"
      >
        {{ item }}
      </text>
    </view>

    <view class="field">
      <text class="field__label">库存有效小时数</text>
      <input class="field__input" type="number" :value="maxAgeHours" :disabled="busy" @input="maxAgeHours = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">最低销量</text>
      <input class="field__input" type="number" :value="minQuantity" :disabled="busy" @input="minQuantity = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">毛利率上限 %</text>
      <input class="field__input" :value="maxMarginPercent" :disabled="busy" @input="maxMarginPercent = inputValue($event)" />
    </view>
    <ActionButton label="生成跨店摘要" variant="primary" block :disabled="busy" @tap="calculate" />

    <template v-if="saved !== null">
      <text class="section-title">摘要 #{{ saved.id }} · {{ saved.status }}</text>
      <FactLine label="保存时间" :value="saved.created_at" :zone="zone" />
      <text v-if="saved.snapshot === null" class="warn">摘要正文已清除，范围与审计记录仍保留。</text>
      <view class="row">
        <ActionButton label="按原范围重算" :disabled="busy" @tap="reuseScope(saved)" />
        <ActionButton label="清除摘要正文" :disabled="busy || saved.snapshot === null" @tap="clearReport(saved.id)" />
      </view>
    </template>

    <template v-if="result !== null">
      <text v-if="stale" class="warn">此报告依赖来源或库存时效已变化，请重新生成。</text>
      <FactLine label="本期 / 对比" :value="`${result.scope.start_date} 至 ${result.scope.end_date} / ${comparisonText(result)}`" />
      <FactLine label="计算时间 / 有效至" :value="`${businessTimeText(result.calculated_at, zone)} / ${result.valid_until === null || result.valid_until === undefined ? '按来源版本判断' : businessTimeText(result.valid_until, zone)}`" />

      <text class="section-title">分币种汇总</text>
      <view v-for="total in result.totals ?? []" :key="total.currency" class="card">
        <text class="card__title">{{ total.currency }} 汇总</text>
        <FactLine label="覆盖店铺" :value="(total.shop_ids ?? []).join(' / ')" />
        <FactLine
          v-for="field in totalFields"
          :key="field.key"
          :label="field.label"
          :value="totalValue(total, field.key)"
        />
        <text class="hint">覆盖说明：{{ (total.warnings ?? []).length === 0 ? '服务端未返回覆盖警告' : (total.warnings ?? []).join(' / ') }}</text>
      </view>
      <view v-if="(result.totals ?? []).length === 0" class="card">
        <text class="hint">当前范围没有可分币种汇总的数据。</text>
      </view>

      <text class="section-title">经营摘要</text>
      <view v-for="line in result.summary ?? []" :key="line" class="card">
        <text class="hint">{{ line }}</text>
      </view>
      <text class="hint">口径与未获取项：{{ (result.limitations ?? []).length === 0 ? '服务端未返回限制说明' : (result.limitations ?? []).join(' / ') }}</text>

      <text class="section-title">各店铺依据</text>
      <view v-for="shop in result.shops ?? []" :key="shop.shop_id" class="card">
        <text class="card__title">{{ shop.shop_name }}</text>
        <FactLine label="店铺 / 平台 / 市场" :value="`${shop.shop_id} / ${shop.platform} / ${shop.market}`" />
        <FactLine label="来源版本" :value="shop.source_revision" />
        <view v-for="group in shop.currencies ?? []" :key="`${shop.shop_id}:${group.currency}`">
          <view class="divider" />
          <text class="card__title">{{ group.currency }} · 本期</text>
          <FactLine label="销售变化 / 变化率" :value="`${moneyText(group.sales_change, group.currency)} / ${group.sales_change_percent === null || group.sales_change_percent === undefined ? '未知' : `${group.sales_change_percent}%`}`" />
          <text class="hint">本期金额与订单依据</text>
          <FactLine label="销售额 / 已知销售小计" :value="`${moneyText(group.current?.analysis?.summary?.sales, group.currency)} / ${moneyText(group.current?.analysis?.summary?.known_sales_subtotal, group.currency)}`" />
          <FactLine label="成本 / 已知毛利" :value="`${moneyText(group.current?.analysis?.summary?.cost, group.currency)} / ${moneyText(group.current?.analysis?.summary?.gross_profit, group.currency)}`" />
          <FactLine label="订单数 / 待履约订单" :value="`${factText(group.current?.orders)} / ${factText(group.current?.pending_orders)}`" />
          <FactLine label="退款 / 已知退款 / 已知行数" :value="`${moneyText(group.current?.refunds, group.currency)} / ${moneyText(group.current?.known_refunds, group.currency)} / ${factText(group.current?.refund_known_lines)}`" />
          <FactLine label="未知履约行数" :value="group.current?.unknown_fulfillment_lines" />
          <FactLine label="购买数量前五 SKU" :value="(group.current?.top_skus ?? []).length === 0 ? '未知' : (group.current?.top_skus ?? []).join(' / ')" />
          <text class="hint">对比期金额与订单依据</text>
          <FactLine label="销售额 / 已知销售小计" :value="`${moneyText(group.comparison?.analysis?.summary?.sales, group.currency)} / ${moneyText(group.comparison?.analysis?.summary?.known_sales_subtotal, group.currency)}`" />
          <FactLine label="成本 / 已知毛利" :value="`${moneyText(group.comparison?.analysis?.summary?.cost, group.currency)} / ${moneyText(group.comparison?.analysis?.summary?.gross_profit, group.currency)}`" />
          <FactLine label="订单数 / 待履约订单" :value="`${factText(group.comparison?.orders)} / ${factText(group.comparison?.pending_orders)}`" />
          <FactLine label="对比期待更新来源" :value="(group.comparison?.pending_sources ?? []).length === 0 ? '无' : `${(group.comparison?.pending_sources ?? []).length} 条`" />
        </view>
        <view class="divider" />
        <FactLine label="低库存数 / 未知数" :value="`${factText(shop.inventory_low)} / ${factText(shop.inventory_unknown)}`" />
        <view v-for="stock in shop.inventory ?? []" :key="`${shop.shop_id}:stock:${stock.id}`">
          <FactLine :label="`库存 ${stock.sku}`" :value="`${stock.available} / 阈值 ${stock.safety_threshold} · ${labelOf(inventoryStatuses, stock.status)} · ${stock.reason} · ${businessTimeText(stock.snapshot_at, zone)}`" />
        </view>
        <FactLine label="消息数" :value="shop.message_count" />
        <view v-for="message in shop.messages ?? []" :key="`${shop.shop_id}:msg:${message.message_id}`">
          <FactLine :label="`消息 ${message.message_id}`" :value="`${message.channel} · ${businessTimeText(message.sent_at, zone)} · ${message.source.filename} 第 ${message.source.row_number} 行`" />
        </view>
        <view v-for="task in shop.tasks ?? []" :key="`${shop.shop_id}:task:${task.id}`">
          <FactLine :label="`待办 #${task.id}`" :value="`${labelOf(workKinds, task.kind)} · ${labelOf(taskLabels, task.status)} · ${labelOf(sourceLabels, task.source_status)}`" />
        </view>
        <text v-if="shop.tasks_has_more" class="hint">还有更多待办，切换到该店后可在待办入口查看。</text>
      </view>
      <text class="hint">
        最近更新的来源：{{ (allSources(result) ?? []).length === 0 ? '服务端未返回来源' : `${(allSources(result) ?? []).length} 条` }}
      </text>

      <ActionButton label="保存持久摘要" variant="primary" block :disabled="busy" @tap="saveReport" />
    </template>

    <text class="section-title">历史摘要</text>
    <view class="row">
      <ActionButton label="刷新状态" :disabled="busy" @tap="load" />
    </view>
    <view v-if="history.length === 0 && !busy" class="card">
      <text class="hint">暂无已保存摘要。</text>
    </view>
    <view v-for="item in history" :key="item.id" class="card">
      <text class="card__title">摘要 #{{ item.id }} · {{ item.status }}</text>
      <text class="hint">{{ businessTimeText(item.created_at, zone) }} · 店铺 {{ (item.scope.shop_ids ?? []).join(' / ') }}</text>
      <text class="hint">{{ item.scope.start_date }} 至 {{ item.scope.end_date }} · {{ item.scope.timezone }}</text>
      <view class="row">
        <ActionButton label="回读摘要" :disabled="busy" @tap="inspect(item.id)" />
        <ActionButton label="按原范围重算" :disabled="busy" @tap="reuseScope(item)" />
        <ActionButton label="清除摘要正文" :disabled="busy || item.snapshot === null" @tap="clearReport(item.id)" />
      </view>
    </view>
    <ActionButton v-if="nextCursor !== null" label="加载更早摘要" :disabled="busy" @tap="loadOlder" />
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 跨店经营总览：多店、多币种、业务日历与对比区间、持久摘要与清除。
 * 接口（均来自 contracts/ui-contract.json 的 r2.overview）：
 *   POST /api/overview/calculate
 *   POST /api/overview/reports
 *   GET  /api/overview/reports
 *   GET  /api/overview/reports/{report_id}
 *   POST /api/overview/reports/{report_id}/clear
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import ActionButton from '../../ui/ActionButton.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import { ApiError, apiGet, apiPost, asObject, asRows, newRequestId } from '../../core/api'
import { businessTimeText, countText, factText, isValidDate, isDecimalInput, moneyText, shiftIso, todayInZone, zonedIsoFromParts } from '../../core/format'
import { importIdentities, inventoryStatuses, labelOf, sourceLabels, taskLabels, workKinds } from '../../core/labels'
import { ensureSession, perform, shopTimezone, state } from '../../core/store'

interface OverviewScope {
  shop_ids: number[]
  start_date: string
  end_date: string
  timezone: string
  data_identity: string
  comparison_start?: string | null
  comparison_end?: string | null
  currencies: string[]
  max_age_hours: number
  min_quantity: number
  max_margin_percent: string
}

interface SourceReference {
  batch_id: number
  row_id: number
  row_number: number
  filename: string
  imported_at: string
  data_identity: string
  exported_at?: string | null
  sheet_name?: string
  origin?: string
}

interface PeriodAnalysisSummary {
  sales?: string | null
  known_sales_subtotal?: string
  cost?: string | null
  gross_profit?: string | null
  margin_percent?: string | null
}

interface PeriodMetrics {
  analysis?: { summary?: PeriodAnalysisSummary | null; source_revision?: number } | null
  orders?: number | null
  refunds?: string | null
  known_refunds?: string | null
  refund_known_lines?: number | null
  pending_orders?: number | null
  unknown_fulfillment_lines?: number | null
  pending_sources?: SourceReference[]
  top_skus?: string[]
}

interface CurrencyGroup {
  currency: string
  current?: PeriodMetrics | null
  comparison?: PeriodMetrics | null
  sales_change?: string | null
  sales_change_percent?: string | null
}

interface CurrencyTotal {
  currency: string
  shop_ids: number[]
  sales?: string | null
  known_sales?: string | null
  comparison_sales?: string | null
  sales_change?: string | null
  sales_change_percent?: string | null
  gross_profit?: string | null
  known_gross_profit?: string | null
  refunds?: string | null
  known_refunds?: string | null
  observed_orders?: number
  warnings?: string[]
}

interface InventoryItem {
  id: number
  sku: string
  channel: string
  available: number
  safety_threshold: number
  status: string
  reason: string
  snapshot_at: string
}

interface MessageEvidence {
  message_id: string
  channel: string
  sent_at: string
  source: SourceReference
}

interface ShopOverview {
  shop_id: number
  shop_name: string
  platform: string
  market: string
  source_revision: number
  currencies: CurrencyGroup[]
  inventory: InventoryItem[]
  inventory_low?: number | null
  inventory_unknown: number
  messages: MessageEvidence[]
  message_count?: number | null
  tasks: Array<{ id: number; kind: string; status: string; source_status: string }>
  tasks_has_more: boolean
  sources: SourceReference[]
}

interface OverviewResult {
  scope: OverviewScope
  engine?: string
  calculated_at: string
  valid_until?: string | null
  shops: ShopOverview[]
  totals: CurrencyTotal[]
  summary: string[]
  limitations: string[]
}

interface OverviewSaved {
  id: number
  status: string
  created_at: string
  scope: OverviewScope
  snapshot: OverviewResult | null
}

const quickRanges = [
  { days: 1, label: '日摘要' },
  { days: 7, label: '周摘要' },
  { days: 30, label: '30 日摘要' },
]

const totalFields = [
  { key: 'sales', label: '销售额' },
  { key: 'known_sales', label: '已知销售小计' },
  { key: 'comparison_sales', label: '对比销售额' },
  { key: 'sales_change', label: '销售变化' },
  { key: 'sales_change_percent', label: '销售变化率 %' },
  { key: 'gross_profit', label: '商品毛利' },
  { key: 'known_gross_profit', label: '已知毛利小计' },
  { key: 'refunds', label: '退款' },
  { key: 'known_refunds', label: '已知退款小计' },
  { key: 'observed_orders', label: '观测订单数' },
]

const currencies = ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']

const selectedShops = ref<number[]>([])
const identity = ref('user_import')
const zoneInput = ref('')
const startDay = ref('')
const endDay = ref('')
const customComparison = ref(false)
const comparisonStart = ref('')
const comparisonEnd = ref('')
const selectedCurrencies = ref<string[]>([])
const maxAgeHours = ref('24')
const minQuantity = ref('1')
const maxMarginPercent = ref('20')
const result = ref<OverviewResult | null>(null)
const saved = ref<OverviewSaved | null>(null)
const history = ref<OverviewSaved[]>([])
const nextCursor = ref<number | null>(null)
const stale = ref(false)
const busy = ref(false)
const error = ref('')
const successText = ref('')
const ready = ref(false)

const zone = computed(() => zoneInput.value.trim() === '' ? shopTimezone() : zoneInput.value.trim())
const identityOptions = computed(() => Object.entries(importIdentities).map(([key, label]) => ({ key, label })))
const identityIndex = computed(() => Math.max(0, Object.keys(importIdentities).indexOf(identity.value)))

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

function toggleShop(shopId: number): void {
  selectedShops.value = selectedShops.value.includes(shopId)
    ? selectedShops.value.filter((item) => item !== shopId)
    : [...selectedShops.value, shopId]
}

function toggleCurrency(currency: string): void {
  selectedCurrencies.value = selectedCurrencies.value.includes(currency)
    ? selectedCurrencies.value.filter((item) => item !== currency)
    : [...selectedCurrencies.value, currency]
}

function totalValue(total: CurrencyTotal, key: string): unknown {
  const amountKeys = [
    'sales', 'known_sales', 'comparison_sales', 'sales_change',
    'gross_profit', 'known_gross_profit', 'refunds', 'known_refunds',
  ]
  const value = (total as unknown as Record<string, unknown>)[key]
  if (amountKeys.includes(key)) return moneyText(value, total.currency)
  if (key === 'sales_change_percent') {
    return value === null || value === undefined ? '未知' : `${value}%`
  }
  return countText(value)
}

function comparisonText(value: OverviewResult): string {
  const start = value.scope.comparison_start ?? null
  const end = value.scope.comparison_end ?? null
  if (start === null && end === null) return '紧邻本期之前的等长区间'
  return `${factText(start)} 至 ${factText(end)}`
}

function allSources(value: OverviewResult): SourceReference[] {
  const rows: SourceReference[] = []
  for (const shop of value.shops ?? []) {
    for (const source of shop.sources ?? []) rows.push(source)
  }
  return rows
}

function applyQuick(days: number): void {
  if (!isValidDate(endDay.value)) {
    error.value = '请先选择合法的结束日期，再使用快捷摘要。'
    return
  }
  const end = zonedIsoFromParts(endDay.value, '00:00', zone.value)
  if (end === null) {
    error.value = '业务时区无法换算，请核对时区。'
    return
  }
  const start = shiftIso(end, -days, zone.value)
  if (start === null) {
    error.value = '无法换算开始日期，请核对时区。'
    return
  }
  startDay.value = start.slice(0, 10)
  success(`已按 ${days} 天设置本期范围。`)
}

function scopePayload(): OverviewScope {
  if (selectedShops.value.length === 0 || selectedShops.value.length > 20) {
    throw new Error('请选择 1–20 家店铺。')
  }
  if (!isValidDate(startDay.value) || !isValidDate(endDay.value)) {
    throw new Error('请填写 YYYY-MM-DD 形式的有效业务日期。')
  }
  if (startDay.value >= endDay.value) {
    throw new Error('结束日期必须晚于开始日期，统计区间为 [开始, 结束)。')
  }
  if (customComparison.value) {
    if (!isValidDate(comparisonStart.value) || !isValidDate(comparisonEnd.value)) {
      throw new Error('自选对比区间需要合法的开始与结束日期。')
    }
  }
  if (!/^\d+$/.test(maxAgeHours.value.trim()) || !/^\d+$/.test(minQuantity.value.trim())) {
    throw new Error('请核对库存小时数、最低销量与毛利率阈值。')
  }
  if (!isDecimalInput(maxMarginPercent.value)) {
    throw new Error('毛利率上限须为数字。')
  }
  return {
    shop_ids: selectedShops.value,
    start_date: startDay.value,
    end_date: endDay.value,
    timezone: zone.value,
    data_identity: identity.value,
    comparison_start: customComparison.value ? comparisonStart.value : null,
    comparison_end: customComparison.value ? comparisonEnd.value : null,
    currencies: selectedCurrencies.value,
    max_age_hours: Number(maxAgeHours.value.trim()),
    min_quantity: Number(minQuantity.value.trim()),
    max_margin_percent: maxMarginPercent.value.trim(),
  }
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  zoneInput.value = shopTimezone()
  const today = todayInZone(zone.value)
  if (endDay.value === '' && today !== null) {
    endDay.value = today
    const start = zonedIsoFromParts(today, '00:00', zone.value)
    const week = start === null ? null : shiftIso(start, -7, zone.value)
    startDay.value = week === null ? today : week.slice(0, 10)
  }
  if (selectedShops.value.length === 0) {
    selectedShops.value = state.shops.map((shop) => shop.id).slice(0, 20)
  }
  await load()
})

async function load(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    const page = asObject<{ items: OverviewSaved[]; next_cursor: number | null }>(
      await apiGet('/api/overview/reports'),
    )
    history.value = asRows<OverviewSaved>(page?.items)
    nextCursor.value = page?.next_cursor ?? null
    const current = saved.value
    if (result.value !== null && current !== null) {
      const revision = asObject<OverviewSaved>(await apiGet(`/api/overview/reports/${current.id}`))
      if (revision !== null && revision.status !== 'current') stale.value = true
    }
  })
  error.value = message
}

async function loadOlder(): Promise<void> {
  const cursor = nextCursor.value
  if (cursor === null) return
  const message = await perform(async () => {
    const page = asObject<{ items: OverviewSaved[]; next_cursor: number | null }>(
      await apiGet('/api/overview/reports', { before: cursor }),
    )
    const incoming = asRows<OverviewSaved>(page?.items)
    history.value = [
      ...history.value,
      ...incoming.filter((item) => !history.value.some((old) => old.id === item.id)),
    ]
    nextCursor.value = page?.next_cursor ?? null
  })
  error.value = message
}

async function calculate(): Promise<void> {
  const message = await perform(async () => {
    const scope = scopePayload()
    const value = asObject<OverviewResult>(await apiPost('/api/overview/calculate', scope))
    if (value === null) throw new Error('总览响应无法读取，请刷新重试。')
    result.value = value
    saved.value = null
    stale.value = false
  })
  if (message === '') success('跨店摘要已生成，请核对分币种依据与未获取项。')
  else error.value = message
}

async function saveReport(): Promise<void> {
  const current = result.value
  if (current === null) return
  const expected: Record<string, number> = {}
  for (const shop of current.shops ?? []) expected[`${shop.shop_id}`] = shop.source_revision
  const modal = await Taro.showModal({
    title: '保存持久摘要',
    content: `保存后按各店来源版本判断时效；来源或库存过期时需要重新生成。`,
    confirmText: '保存',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<OverviewSaved>(
      await apiPost('/api/overview/reports', {
        request_id: newRequestId(),
        scope: current.scope,
        expected_revisions: expected,
      }),
    )
    if (value === null) throw new Error('保存响应无法读取，请到历史摘要回读核对。')
    saved.value = value
    await load()
  }, '跨店摘要已保存，库存按保存时刻再次核验。', '历史摘要')
}

async function inspect(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<OverviewSaved>(await apiGet(`/api/overview/reports/${id}`))
    if (value === null) throw new Error('摘要响应无法读取，请刷新重试。')
    saved.value = value
    result.value = value.snapshot
    stale.value = value.status !== 'current'
  })
  error.value = message
}

function reuseScope(item: OverviewSaved): void {
  const scope = item.scope
  selectedShops.value = scope.shop_ids ?? []
  startDay.value = scope.start_date
  endDay.value = scope.end_date
  identity.value = scope.data_identity
  zoneInput.value = scope.timezone
  selectedCurrencies.value = scope.currencies ?? []
  maxAgeHours.value = `${scope.max_age_hours}`
  minQuantity.value = `${scope.min_quantity}`
  maxMarginPercent.value = `${scope.max_margin_percent}`
  const comparison = scope.comparison_start !== null && scope.comparison_start !== undefined
  customComparison.value = comparison
  comparisonStart.value = scope.comparison_start ?? ''
  comparisonEnd.value = scope.comparison_end ?? ''
  success('已恢复摘要范围，请重新生成。')
}

async function clearReport(id: number): Promise<void> {
  const modal = await Taro.showModal({
    title: `清除摘要 #${id}`,
    content: '摘要正文与来源依赖将被清除，保留范围、状态和审计记录。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    await apiPost(`/api/overview/reports/${id}/clear`, { confirm: true })
    await inspect(id)
    await load()
  }, '摘要正文已清除。', '历史摘要')
}
</script>
