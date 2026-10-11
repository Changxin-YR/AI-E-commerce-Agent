<template>
  <PageShell
    title="结算回款"
    subtitle="人工登记到账凭据，逐笔与平台回款比较；人工到账仍须核验银行证据。"
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

    <text class="section-title">结算记录</text>
    <FactLine label="结算记录" :value="record === null ? '尚未保存结算记录' : `#${record.id} · v${record.version} · ${labelOf(settlementStatuses, record.status)}`" />
    <view class="row">
      <ActionButton v-if="record" label="回读最新存档" :disabled="busy" @tap="openRecord(record.id)" />
      <ActionButton label="核对当前来源" :disabled="busy || record === null" @tap="reloadCurrent" />
      <ActionButton label="新建结算记录" :disabled="busy" @tap="resetRecord" />
    </view>
    <view class="field">
      <text class="field__label">原始账单号</text>
      <input class="field__input" :value="statementId" :disabled="busy || locked" @input="statementId = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">结算周期与核查说明</text>
      <input class="field__input" :value="note" :disabled="busy || locked" @input="note = inputValue($event)" />
    </view>

    <text class="section-title">卖家人工到账登记</text>
    <text class="hint">按平台回款凭据号逐笔关联；人工登记的银行到账仍须核验银行证据。最多 50 条。</text>
    <view v-for="(receipt, index) in receipts" :key="`${index}:${receipt.payoutRef}`" class="card">
      <text class="card__title">回款 {{ receipt.payoutRef === '' ? '凭据号未知' : receipt.payoutRef }}</text>
      <text class="hint">人工登记凭据 {{ factText(receipt.receiptRef) }}</text>
      <FactLine label="人工到账金额 / 币种" :value="moneyText(receipt.amount, receipt.currency)" />
      <FactLine label="到账时间" :value="`${receipt.receivedDay} ${receipt.receivedClock} · ${receipt.timezone}`" />
      <FactLine label="依据" :value="receipt.note" />
      <view class="row">
        <ActionButton label="修改登记" :disabled="busy || locked" @tap="editReceipt(index)" />
        <ActionButton label="移除本条" :disabled="busy || locked" @tap="removeReceipt(index)" />
      </view>
    </view>
    <view v-if="receipts.length === 0" class="card">
      <text class="hint">尚未登记到账。可先添加一条带银行证据说明的到账登记。</text>
    </view>
    <ActionButton :label="`添加到账登记（${receipts.length}/50）`" :disabled="busy || locked || receipts.length >= 50" @tap="editReceipt(receipts.length)" />

    <template v-if="receiptIndex !== null">
      <text class="section-title">人工到账登记</text>
      <view class="field">
        <text class="field__label">平台回款凭据号</text>
        <input class="field__input" :value="receiptForm.payoutRef" :disabled="busy" @input="receiptForm.payoutRef = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">到账凭据号</text>
        <input class="field__input" :value="receiptForm.receiptRef" :disabled="busy" @input="receiptForm.receiptRef = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">到账金额（须大于 0）</text>
        <input class="field__input" :value="receiptForm.amount" :disabled="busy" @input="receiptForm.amount = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">到账币种</text>
        <input class="field__input" :value="receiptForm.currency" :disabled="busy" @input="receiptForm.currency = inputValue($event).toUpperCase()" />
      </view>
      <view class="field">
        <text class="field__label">到账日期</text>
        <picker mode="date" :value="receiptForm.receivedDay" @change="receiptForm.receivedDay = pickerValue($event)">
          <view class="field__picker">{{ receiptForm.receivedDay === '' ? '请选择到账日期' : receiptForm.receivedDay }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">到账时间</text>
        <picker mode="time" :value="receiptForm.receivedClock" @change="receiptForm.receivedClock = pickerValue($event)">
          <view class="field__picker">{{ receiptForm.receivedClock }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">到账时区（IANA）</text>
        <input class="field__input" :value="receiptForm.timezone" :disabled="busy" @input="receiptForm.timezone = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">银行证据来源与核对说明</text>
        <input class="field__input" :value="receiptForm.note" :disabled="busy" @input="receiptForm.note = inputValue($event)" />
      </view>
      <view class="row">
        <ActionButton label="采用本条登记" variant="primary" :disabled="busy" @tap="applyReceipt" />
        <ActionButton label="取消" :disabled="busy" @tap="receiptIndex = null" />
      </view>
    </template>

    <view class="row">
      <ActionButton label="预览逐笔回款核对" variant="primary" :disabled="busy || locked" @tap="preview" />
    </view>

    <template v-if="record !== null">
      <text v-if="record.snapshot === null" class="warn">正文已清除，版本与审计记录仍保留。</text>
      <template v-else>
        <text class="section-title">保存时完整依据</text>
        <text class="hint">
          结算说明 {{ record.snapshot.content.note }} · 来源修订 {{ record.snapshot.source_revision }} ·
          {{ businessTimeText(record.snapshot.calculated_at, zone) }}
        </text>
      </template>
    </template>

    <template v-if="previewSnapshot !== null">
      <text class="section-title">原账单 {{ previewSnapshot.content.statement_id }}</text>
      <FactLine label="期间" :value="`${previewSnapshot.scope.start_at} 至 ${previewSnapshot.scope.end_at}`" :zone="zone" />
      <FactLine label="业务时区" :value="previewSnapshot.scope.timezone" />
      <FactLine label="来源修订" :value="previewSnapshot.source_revision" />
      <FactLine label="核对时间" :value="previewSnapshot.calculated_at" :zone="zone" />
      <FactLine label="结算说明" :value="previewSnapshot.content.note" />
      <text class="hint">覆盖完整性未知 · 期初期末余额未知 · 银行证据待核验</text>
      <FactLine label="核对时间戳来源" :value="previewHash === null ? '尚未预览' : `预览指纹 ${previewHash.slice(0, 12)}…`" />
      <view v-for="total in previewSnapshot.totals ?? []" :key="`${total.currency}:${total.entry_type}`" class="card">
        <text class="card__title">{{ total.currency }} · {{ total.entry_type === 'manual_receipt' ? '人工到账登记' : labelOf(entryTypes, total.entry_type) }}</text>
        <text class="hint">{{ total.count }} 笔</text>
        <FactLine label="金额" :value="moneyText(total.amount, total.currency)" />
      </view>
      <FactLine label="周期外明细编号" :value="(previewSnapshot.outside_cycle_ids ?? []).length === 0 ? '无' : (previewSnapshot.outside_cycle_ids ?? []).join('、')" />
      <text v-for="check in previewSnapshot.checks ?? []" :key="check" class="hint">{{ check }}</text>

      <text class="section-title">逐笔回款比较 · 差额为平台减人工</text>
      <view v-for="comparison in previewSnapshot.comparisons ?? []" :key="comparison.payout_ref" class="card">
        <text class="card__title">{{ comparison.payout_ref === '' ? '凭据号未知' : comparison.payout_ref }} · {{ labelOf(comparisonStatuses, comparison.status) }}</text>
        <text class="hint">差额：{{ comparison.difference === null || comparison.difference === undefined ? '无法确定' : comparison.difference }}</text>
        <text class="hint">关联账单行：{{ (comparison.statement_ids ?? []).join(' / ') || '无' }}</text>
        <text class="hint">登记序号：{{ (comparison.receipt_indexes ?? []).map((index) => index + 1).join(' / ') || '无' }}</text>
      </view>
      <view v-if="(previewSnapshot.comparisons ?? []).length === 0" class="card">
        <text class="hint">当前范围没有可比较的平台回款记录。</text>
      </view>

      <text class="section-title">全部原账单行</text>
      <view v-for="item in previewSnapshot.statements ?? []" :key="item.id" class="card">
        <text class="card__title">{{ item.statement_id }} / {{ item.line_id }}</text>
        <FactLine label="收支类型" :value="labelOf(entryTypes, item.entry_type)" />
        <FactLine label="金额 / 币种" :value="moneyText(item.amount, item.currency)" />
        <FactLine label="发生时间" :value="item.occurred_at" :zone="previewSnapshot.scope.timezone" />
        <FactLine label="结算编号" :value="item.settlement_id" />
        <FactLine label="订单号" :value="item.order_id" />
        <FactLine label="源行" :value="`${item.source.filename} · 第 ${item.source.row_number} 行`" />
      </view>
      <text v-if="(previewSnapshot.statements ?? []).length === 0" class="hint">当前范围没有原账单行。</text>

      <text class="section-title">全部人工到账登记</text>
      <view v-for="(receipt, index) in previewSnapshot.content.receipts ?? []" :key="`preview:${index}`" class="card">
        <text class="card__title">登记 {{ index + 1 }} · {{ factText(receipt.payout_ref) }}</text>
        <FactLine label="人工登记凭据" :value="receipt.receipt_ref" />
        <FactLine label="对应平台回款" :value="receipt.payout_ref" />
        <FactLine label="人工到账金额" :value="moneyText(receipt.amount, receipt.currency)" />
        <FactLine label="到账时间" :value="`${receipt.received_at} · ${receipt.timezone}`" :zone="zone" />
        <FactLine label="依据" :value="receipt.note" />
      </view>

      <view class="card" @tap="confirmed = !confirmed">
        <text class="chip" :class="{ 'chip--active': confirmed }">
          {{ confirmed ? '已核对' : '未核对' }} · 已核对逐笔关联、币种、金额、跨期项与到账登记依据
        </text>
      </view>
      <text v-if="pending" class="warn">结果待确认，请核对同次保存请求。</text>
      <text v-if="previewHash === null" class="warn">保存需要当前来源的预览指纹，请先执行“预览逐笔回款核对”。</text>
      <view class="row">
        <ActionButton
          :label="pending ? '核对同次写入' : '保存结算版本'"
          variant="primary"
          :disabled="busy || previewHash === null || (!confirmed && !pending)"
          @tap="save"
        />
        <ActionButton v-if="record" label="撤销记录" :disabled="busy" @tap="control('withdraw')" />
        <ActionButton v-if="record" label="清除正文" :disabled="busy" @tap="control('clear')" />
      </view>
    </template>

    <template v-if="record !== null">
      <text class="section-title">结算版本历史</text>
      <view v-for="history in record.history ?? []" :key="history.version" class="card">
        <text class="card__title">版本 {{ history.version }} · {{ history.action }}</text>
        <text class="hint">{{ businessTimeText(history.created_at, zone) }} · {{ history.has_content ? '含正文' : '正文已清除' }}</text>
      </view>
      <text v-if="(record.history ?? []).length === 0" class="hint">服务端未返回版本历史。</text>
    </template>

    <text class="section-title">结算存档</text>
    <view class="row">
      <ActionButton label="刷新记录" :disabled="busy" @tap="load" />
    </view>
    <view v-if="records.length === 0 && !busy" class="card">
      <text class="hint">当前身份与渠道下暂无结算记录。</text>
    </view>
    <view v-for="item in records" :key="item.id" class="card">
      <text class="card__title">结算 #{{ item.id }} · v{{ item.version }}</text>
      <text class="hint">{{ labelOf(settlementStatuses, item.status) }} · 内容版本 {{ item.content_version }} · {{ businessTimeText(item.created_at, zone) }}</text>
      <ActionButton label="打开结算记录" :disabled="busy" @tap="openRecord(item.id)" />
    </view>
    <ActionButton v-if="nextCursor !== null" label="加载更多记录" :disabled="busy" @tap="loadMore" />
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 结算回款：原账单与期间、最多 50 条人工到账登记、逐笔回款核对预览、
 * 缺口/差异/周期外记录、版本历史与存档。
 * 接口（均来自 contracts/ui-contract.json 的 r2.settlements）：
 *   POST /api/shops/{shop_id}/settlements/preview
 *   POST /api/shops/{shop_id}/settlements
 *   GET  /api/shops/{shop_id}/settlements
 *   GET  /api/shops/{shop_id}/settlements/{settlement_id}
 *   GET  /api/shops/{shop_id}/settlements/{settlement_id}/current
 *   POST /api/shops/{shop_id}/settlements/{settlement_id}/{action}   （withdraw / clear）
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

const settlementStatuses: Record<string, string> = {
  active: '当前有效',
  stale: '来源变化 · 待重核',
  withdrawn: '已撤销',
  cleared: '正文已清除',
}

interface ExpenseScope {
  data_identity: string
  channel: string
  start_at: string
  end_at: string
  timezone: string
}

interface ManualReceipt {
  payout_ref: string
  receipt_ref: string
  amount: string
  currency: string
  received_at: string
  timezone: string
  note: string
}

interface SettlementContent {
  statement_id: string
  note: string
  receipts: ManualReceipt[]
}

interface SourceReference {
  batch_id: number
  row_id: number
  row_number: number
  filename: string
  imported_at: string
}

interface StatementItem {
  id: number
  statement_id: string
  line_id: string
  entry_type: string
  amount: string
  currency: string
  occurred_at: string
  settlement_id: string
  order_id: string
  source: SourceReference
}

interface StatementTotal {
  currency: string
  entry_type: string
  amount: string
  count: number
}

interface PayoutComparison {
  payout_ref: string
  status: string
  statement_ids: number[]
  receipt_indexes: number[]
  difference?: string | null
}

interface SettlementSnapshot {
  scope: ExpenseScope
  content: SettlementContent
  source_revision: number
  calculated_at: string
  statements: StatementItem[]
  totals: StatementTotal[]
  comparisons: PayoutComparison[]
  outside_cycle_ids: number[]
  coverage_status: string
  balance_status: string
  bank_status: string
  checks: string[]
}

interface SettlementPreview {
  preview_hash: string
  snapshot: SettlementSnapshot
}

interface SettlementHistory {
  version: number
  action: string
  has_content: boolean
  created_at: string
}

interface SettlementSaved {
  id: number
  shop_id: number
  data_identity: string
  channel: string
  status: string
  version: number
  content_version: number
  created_at: string
  snapshot: SettlementSnapshot | null
  history: SettlementHistory[]
}

interface ReceiptDraft {
  payoutRef: string
  receiptRef: string
  amount: string
  currency: string
  receivedDay: string
  receivedClock: string
  timezone: string
  note: string
}

function emptyReceipt(): ReceiptDraft {
  return {
    payoutRef: '',
    receiptRef: '',
    amount: '',
    currency: 'USD',
    receivedDay: todayInZone(shopTimezone()) ?? '',
    receivedClock: '12:00',
    timezone: shopTimezone(),
    note: '',
  }
}

const identity = ref('user_import')
const channel = ref('generic')
const startDay = ref('')
const startClock = ref('00:00')
const endDay = ref('')
const endClock = ref('23:59')
const statementId = ref('')
const note = ref('')
const receipts = ref<ReceiptDraft[]>([])
const receiptIndex = ref<number | null>(null)
const receiptForm = ref<ReceiptDraft>(emptyReceipt())
const previewSnapshot = ref<SettlementSnapshot | null>(null)
const previewHash = ref<string | null>(null)
const confirmed = ref(false)
const pending = ref(false)
const pendingKey = ref<string | null>(null)
const record = ref<SettlementSaved | null>(null)
const records = ref<SettlementSaved[]>([])
const nextCursor = ref<number | null>(null)
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
/** 已保存正文锁定：写结果待确认时只允许核对同次写入。 */
const locked = computed(() => pending.value)

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

function contentPayload(): SettlementContent {
  if (statementId.value.trim() === '') throw new Error('请填写原始账单号。')
  if (note.value.trim() === '') throw new Error('请填写结算周期与核查说明。')
  const rows: ManualReceipt[] = receipts.value.map((receipt, index) => {
    if (receipt.payoutRef.trim() === '') throw new Error(`第 ${index + 1} 条登记缺少平台回款凭据号。`)
    if (receipt.receiptRef.trim() === '') throw new Error(`第 ${index + 1} 条登记缺少到账凭据号。`)
    if (!isDecimalInput(receipt.amount) || !/[1-9]/.test(receipt.amount)) {
      throw new Error(`第 ${index + 1} 条登记的到账金额须为大于 0 的数字。`)
    }
    if (receipt.currency.trim() === '') throw new Error(`第 ${index + 1} 条登记缺少币种。`)
    if (!isValidDate(receipt.receivedDay)) throw new Error(`第 ${index + 1} 条登记缺少合法的到账日期。`)
    const receivedAt = zonedIsoFromParts(receipt.receivedDay, receipt.receivedClock, receipt.timezone.trim() === '' ? zone.value : receipt.timezone.trim())
    if (receivedAt === null) throw new Error(`第 ${index + 1} 条登记的到账时间无法换算，请核对时区。`)
    if (receipt.note.trim() === '') throw new Error(`第 ${index + 1} 条登记缺少银行证据来源与核对说明。`)
    return {
      payout_ref: receipt.payoutRef.trim(),
      receipt_ref: receipt.receiptRef.trim(),
      amount: receipt.amount.trim(),
      currency: receipt.currency.trim().toUpperCase(),
      received_at: receivedAt,
      timezone: receipt.timezone.trim() === '' ? zone.value : receipt.timezone.trim(),
      note: receipt.note.trim(),
    }
  })
  return { statement_id: statementId.value.trim(), note: note.value.trim(), receipts: rows }
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  const today = todayInZone(zone.value)
  if (endDay.value === '' && today !== null) endDay.value = today
  if (startDay.value === '' && today !== null) startDay.value = today
  if (receiptForm.value.currency === 'USD') {
    receiptForm.value.currency = state.shops.find((shop) => shop.id === state.shopId)?.currency ?? 'USD'
  }
  await load()
})

async function load(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    const page = asObject<{ items: SettlementSaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/settlements'), {
        data_identity: identity.value,
        channel: channel.value,
      }),
    )
    records.value = asRows<SettlementSaved>(page?.items)
    nextCursor.value = page?.next_cursor ?? null
  })
  error.value = message
}

async function loadMore(): Promise<void> {
  const cursor = nextCursor.value
  if (cursor === null) return
  const message = await perform(async () => {
    const page = asObject<{ items: SettlementSaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/settlements'), {
        data_identity: identity.value,
        channel: channel.value,
        before: cursor,
      }),
    )
    const incoming = asRows<SettlementSaved>(page?.items)
    records.value = [
      ...records.value,
      ...incoming.filter((item) => !records.value.some((old) => old.id === item.id)),
    ]
    nextCursor.value = page?.next_cursor ?? null
  })
  error.value = message
}

function resetRecord(): void {
  record.value = null
  previewSnapshot.value = null
  previewHash.value = null
  confirmed.value = false
  pending.value = false
  pendingKey.value = null
  statementId.value = ''
  note.value = ''
  receipts.value = []
  receiptIndex.value = null
}

function editReceipt(index: number): void {
  const existing = index < receipts.value.length ? receipts.value[index] : null
  receiptIndex.value = index
  receiptForm.value = existing === null
    ? { ...emptyReceipt(), currency: state.shops.find((shop) => shop.id === state.shopId)?.currency ?? 'USD' }
    : { ...existing }
}

function removeReceipt(index: number): void {
  receipts.value = receipts.value.filter((_, position) => position !== index)
  if (receiptIndex.value === index) receiptIndex.value = null
  previewSnapshot.value = null
  previewHash.value = null
  confirmed.value = false
}

function applyReceipt(): void {
  const index = receiptIndex.value
  if (index === null) return
  const next = [...receipts.value]
  next[index] = { ...receiptForm.value }
  receipts.value = next
  receiptIndex.value = null
  previewSnapshot.value = null
  previewHash.value = null
  confirmed.value = false
}

async function preview(): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<SettlementPreview>(
      await apiPost(shopPath('/settlements/preview'), {
        scope: scopePayload(),
        settlement_id: record.value?.id ?? null,
        version: record.value?.version ?? 0,
        content: contentPayload(),
      }),
    )
    if (value === null) throw new Error('预览响应无法读取，请刷新后重试。')
    previewSnapshot.value = value.snapshot
    previewHash.value = value.preview_hash
    // 新预览代表新的保存意图：释放旧的幂等键，避免复用过期请求。
    pending.value = false
    pendingKey.value = null
    confirmed.value = false
  })
  if (message === '') success('已生成逐笔回款核对预览，请核对差异与周期外明细。')
  else error.value = message
}

async function save(): Promise<void> {
  const snapshot = previewSnapshot.value
  const hash = previewHash.value
  if (pending.value && record.value !== null) {
    await openRecord(record.value.id)
    return
  }
  if (snapshot === null || hash === null) {
    error.value = '保存需要当前来源的预览指纹，请先执行“预览逐笔回款核对”。'
    return
  }
  const key = pendingKey.value ?? newRequestId()
  pendingKey.value = key
  await writeAction(async () => {
    const value = asObject<SettlementSaved>(
      await apiPost(shopPath('/settlements'), {
        scope: snapshot.scope,
        settlement_id: record.value?.id ?? null,
        version: record.value?.version ?? 0,
        content: snapshot.content,
        preview_hash: hash,
        request_id: key,
        confirm: true,
      }),
    )
    if (value === null) throw new Error('保存响应无法读取，请到结算存档回读核对。')
    pending.value = false
    pendingKey.value = null
    record.value = value
    // 保存成功后释放预览指纹：再次保存必须先重新预览，避免提交过期依据。
    previewHash.value = null
    confirmed.value = false
    await load()
  }, '结算记录与到账登记已保存。', '结算存档')
}

async function openRecord(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<SettlementSaved>(await apiGet(shopPath(`/settlements/${id}`)))
    if (value === null) throw new Error('结算响应无法读取，请刷新重试。')
    record.value = value
    previewSnapshot.value = value.snapshot
    previewHash.value = null
    confirmed.value = false
    pending.value = false
    pendingKey.value = null
    if (value.snapshot !== null) {
      statementId.value = value.snapshot.content.statement_id
      note.value = value.snapshot.content.note
      receipts.value = (value.snapshot.content.receipts ?? []).map((receipt) => ({
        payoutRef: receipt.payout_ref,
        receiptRef: receipt.receipt_ref,
        amount: `${receipt.amount}`,
        currency: receipt.currency,
        receivedDay: receipt.received_at.slice(0, 10),
        receivedClock: receipt.received_at.slice(11, 16),
        timezone: receipt.timezone,
        note: receipt.note,
      }))
    }
    success('结算记录与到账登记已回读。')
  })
  error.value = message
}

/** 核对当前来源：读取 current，拿到最新来源与预览（尚未重新确认）。 */
async function reloadCurrent(): Promise<void> {
  const current = record.value
  if (current === null) return
  const message = await perform(async () => {
    const value = asObject<{ record: SettlementSaved; preview: SettlementPreview | null }>(
      await apiGet(shopPath(`/settlements/${current.id}/current`)),
    )
    if (value === null) throw new Error('回读响应无法读取，请刷新重试。')
    record.value = value.record
    previewSnapshot.value = value.preview?.snapshot ?? value.record.snapshot
    previewHash.value = value.preview?.preview_hash ?? null
    confirmed.value = false
  })
  error.value = message
}

async function control(action: 'withdraw' | 'clear'): Promise<void> {
  const current = record.value
  if (current === null) return
  const modal = await Taro.showModal({
    title: action === 'clear' ? '清除结算正文' : '撤销结算记录',
    content: action === 'clear' ? '清除登记与历史快照的正文及依据，无法恢复。' : '撤销本次人工结算记录，保留历史。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<SettlementSaved>(
      await apiPost(shopPath(`/settlements/${current.id}/${action}`), {
        request_id: newRequestId(),
        version: current.version,
        confirm: true,
      }),
    )
    if (value !== null) record.value = value
    await load()
  }, '结算状态已更新。', '结算存档')
}
</script>
