<template>
  <PageShell
    title="费用映射规则"
    subtitle="用账单中的费用名称映射费用类别；预览只比较所选期间，避免在不知影响范围的情况下保存。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <FactLine label="所属店铺" :value="shopName" />
    <FactLine label="业务时区" :value="zone" />

    <text class="section-title">适用范围</text>
    <view class="field">
      <text class="field__label">数据身份</text>
      <picker mode="selector" :range="identityOptions" range-key="label" :value="identityIndex" @change="setIdentity($event)">
        <view class="field__picker">{{ labelOf(importIdentities, identity) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">来源渠道</text>
      <picker mode="selector" :range="channelOptions" range-key="label" :value="channelIndex" @change="setChannel($event)">
        <view class="field__picker">{{ labelOf(importChannels, channel) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">开始日期</text>
      <picker mode="date" :value="startDay" @change="setStartDay($event)">
        <view class="field__picker">{{ startDay === '' ? '请选择开始日期' : startDay }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">开始时间</text>
      <picker mode="time" :value="startClock" @change="setStartClock($event)">
        <view class="field__picker">{{ startClock }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">结束日期（区间为 [开始, 结束)）</text>
      <picker mode="date" :value="endDay" @change="setEndDay($event)">
        <view class="field__picker">{{ endDay === '' ? '请选择结束日期' : endDay }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">结束时间</text>
      <picker mode="time" :value="endClock" @change="setEndClock($event)">
        <view class="field__picker">{{ endClock }}</view>
      </picker>
    </view>
    <text class="hint">保存的规则作用于相同数据身份与渠道；期间只决定预览比较哪些账单行。</text>

    <text class="section-title">规则内容</text>
    <FactLine
      label="当前规则"
      :value="ruleRecord === null
        ? '尚未选择规则 · 将新建一条规则'
        : `#${ruleRecord.id} · v${ruleRecord.version} · ${labelOf(ruleStatuses, ruleRecord.status)}`"
    />
    <view class="row">
      <ActionButton v-if="ruleRecord" label="回读最新规则" :disabled="locked || ruleRecord === null" @tap="openRule(ruleRecord.id)" />
      <ActionButton label="新建另一规则" :disabled="locked" @tap="resetDraft" />
    </view>
    <view class="field">
      <text class="field__label">账单费用名称（按服务端标准化后精确匹配，最多 120 字）</text>
      <input class="field__input" :value="form.feeName" :disabled="locked" @input="setFeeName($event)" />
    </view>
    <view class="field">
      <text class="field__label">归入类别</text>
      <picker mode="selector" :range="categoryOptions" range-key="label" :value="categoryIndex" @change="setCategory($event)">
        <view class="field__picker">{{ labelOf(expenseCategories, form.category) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">分类与修订依据（最多 500 字）</text>
      <input class="field__input" :value="form.reason" :disabled="locked" @input="setReason($event)" />
    </view>
    <view class="row">
      <ActionButton label="预览映射变化" variant="primary" :disabled="locked" @tap="preview" />
      <ActionButton label="刷新规则列表" :disabled="locked" @tap="load" />
    </view>

    <template v-if="previewResult !== null">
      <text class="section-title">待确认的分类变化</text>
      <FactLine label="当前来源修订" :value="previewResult.source_revision" />
      <FactLine label="受检账单行数" :value="previewResult.statement_count" />
      <FactLine label="预览时间" :value="previewResult.calculated_at" :zone="zone" />
      <FactLine label="原规则" :value="previewResult.previous === null ? '无 · 新建规则' : contentText(previewResult.previous)" />
      <FactLine label="拟保存规则" :value="contentText(previewResult.proposed)" />
      <text v-if="(previewResult.changes ?? []).length === 0" class="hint">所选期间内没有账单行的分类会因此规则变化；保存后仅影响之后的核对。</text>
      <view v-for="change in previewResult.changes ?? []" :key="`${change.statement_id}:${change.fee_name}`" class="card">
        <text class="card__title">账单行 #{{ change.statement_id }} · {{ change.fee_name }}</text>
        <text class="hint">原：{{ mappingText(change.before) }}</text>
        <text class="hint">新：{{ mappingText(change.after) }}</text>
        <SourceEvidence :source="change.source" :zone="zone" />
      </view>
      <view class="card" @tap="confirmed = !confirmed">
        <text class="chip" :class="{ 'chip--active': confirmed }">
          {{ confirmed ? '已核对' : '未核对' }} · 已核对受影响的账单行、类别与映射依据
        </text>
      </view>
      <text v-if="pending" class="warn">上次写入结果未知：表单与范围已锁定，请用“核对同次写入”核对保存结果后再决定。</text>
      <view class="row">
        <ActionButton
          :label="pending ? '核对同次写入' : '保存已预览规则'"
          variant="primary"
          :disabled="busy || (!confirmed && !pending)"
          @tap="save"
        />
        <ActionButton v-if="ruleRecord" label="撤销规则" :disabled="locked" @tap="control('withdraw')" />
        <ActionButton v-if="ruleRecord" label="清除规则正文" :disabled="locked" @tap="control('clear')" />
      </view>
    </template>

    <template v-if="ruleRecord !== null">
      <text class="section-title">规则版本历史</text>
      <view v-for="history in ruleRecord.history ?? []" :key="history.version" class="card">
        <text class="card__title">版本 {{ history.version }} · {{ history.action }}</text>
        <text class="hint">{{ businessTimeText(history.created_at, zone) }}</text>
        <FactLine v-if="history.content" label="费用名称 → 类别" :value="contentText(history.content)" />
        <text v-else class="hint">正文已清除</text>
      </view>
      <text v-if="(ruleRecord.history ?? []).length === 0" class="hint">服务端未返回版本历史。</text>
    </template>

    <text class="section-title">范围内的规则记录</text>
    <view v-if="rules.length === 0 && !busy" class="card">
      <text class="hint">当前身份与渠道下暂无费用映射规则。可先预览并保存第一条规则。</text>
    </view>
    <view v-for="item in rules" :key="item.id" class="card">
      <text class="card__title">#{{ item.id }} {{ item.content === null ? '正文已清除' : factText(item.content.fee_name) }}</text>
      <text class="hint">
        {{ item.content === null ? '类别已清除' : labelOf(expenseCategories, item.content.category) }} ·
        {{ labelOf(ruleStatuses, item.status) }} · 版本 {{ item.version }} ·
        {{ businessTimeText(item.created_at, zone) }}
      </text>
      <ActionButton label="打开规则" :disabled="locked" @tap="openRule(item.id)" />
    </view>
    <ActionButton v-if="nextCursor !== null" label="加载更多规则" :disabled="locked" @tap="loadMore" />
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 费用映射规则：账单费用名称到费用类别的映射规则。
 * 先预览影响范围（受检账单行、原规则、拟保存规则与逐行变化），核对后再保存；
 * 必填项留空不提交，写操作断线 / 超时按“结果未知，请回读”处理。
 * 接口（均来自 contracts/ui-contract.json 的 r2.expenses）：
 *   GET  /api/shops/{shop_id}/fee-rules
 *   POST /api/shops/{shop_id}/fee-rules/preview
 *   POST /api/shops/{shop_id}/fee-rules
 *   GET  /api/shops/{shop_id}/fee-rules/{rule_id}
 *   POST /api/shops/{shop_id}/fee-rules/{rule_id}/{action}   （withdraw / clear）
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import ActionButton from '../../ui/ActionButton.vue'
import SourceEvidence from '../../ui/SourceEvidence.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import { ApiError, apiGet, apiPost, asObject, asRows, newRequestId } from '../../core/api'
import { businessTimeText, factText, isValidDate, todayInZone, zonedIsoFromParts } from '../../core/format'
import { importChannels, importIdentities, labelOf } from '../../core/labels'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

/** 费用类别：与后端 Category 及 Flutter finance_common.dart 一致。 */
const expenseCategories: Record<string, string> = {
  shipping: '物流',
  packaging: '包装',
  storage: '仓储',
  platform: '平台服务',
  advertising: '广告',
  tax: '税费',
  other: '其他费用',
}

/** 规则状态（后端 FeeRuleSaved.status）。 */
const ruleStatuses: Record<string, string> = {
  active: '当前有效',
  withdrawn: '已撤销',
  cleared: '正文已清除',
}

/** 账单行分类结果（后端 FeeMapping.status）。 */
const mappingStatuses: Record<string, string> = {
  mapped: '已按规则分类 · 业务待核',
  unmapped: '未匹配规则',
  ambiguous: '重复凭据或规则',
  currency_mismatch: '币种不一致',
  category_conflict: '与人工费用类别冲突',
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
  source: SourceReference
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

interface RuleDraft {
  feeName: string
  category: string
  reason: string
}

function emptyDraft(): RuleDraft {
  return { feeName: '', category: 'platform', reason: '' }
}

const identity = ref('user_import')
const channel = ref('generic')
const startDay = ref('')
const startClock = ref('00:00')
const endDay = ref('')
const endClock = ref('23:59')
const form = ref<RuleDraft>(emptyDraft())
const rules = ref<FeeRuleSaved[]>([])
const nextCursor = ref<number | null>(null)
const ruleRecord = ref<FeeRuleSaved | null>(null)
const previewResult = ref<FeeRulePreview | null>(null)
const confirmed = ref(false)
const pending = ref(false)
const pendingKey = ref<string | null>(null)
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
/** 写结果待确认或请求进行中时锁定表单，避免在未知状态下改口径。 */
const locked = computed(() => busy.value || pending.value)

function success(text: string): void {
  successText.value = text
  void Taro.showToast({ title: text, icon: 'none' })
}

/** 写操作：断线 / 超时提示“结果未知，请回读”，不推断成功。 */
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

/** 任何表单或范围修改都会让预览指纹失效，必须重新预览后才允许保存。 */
function invalidatePreview(): void {
  previewResult.value = null
  confirmed.value = false
  pending.value = false
  pendingKey.value = null
}

function contentText(content: FeeRuleContent): string {
  return `${factText(content.fee_name)} → ${labelOf(expenseCategories, content.category)} · 依据：${factText(content.reason)}`
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

/** 期间载荷：客户端只做时区换算，不触碰金额。 */
function scopePayload(): Record<string, string> {
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

function setIdentity(event: unknown): void {
  if (locked.value) return
  identity.value = identityOptions.value[Number(pickerValue(event))]?.key ?? 'user_import'
  ruleRecord.value = null
  rules.value = []
  nextCursor.value = null
  invalidatePreview()
}

function setChannel(event: unknown): void {
  if (locked.value) return
  channel.value = channelOptions.value[Number(pickerValue(event))]?.key ?? 'generic'
  ruleRecord.value = null
  rules.value = []
  nextCursor.value = null
  invalidatePreview()
}

function setStartDay(event: unknown): void {
  if (locked.value) return
  startDay.value = pickerValue(event)
  invalidatePreview()
}

function setStartClock(event: unknown): void {
  if (locked.value) return
  startClock.value = pickerValue(event)
  invalidatePreview()
}

function setEndDay(event: unknown): void {
  if (locked.value) return
  endDay.value = pickerValue(event)
  invalidatePreview()
}

function setEndClock(event: unknown): void {
  if (locked.value) return
  endClock.value = pickerValue(event)
  invalidatePreview()
}

function setFeeName(event: unknown): void {
  if (locked.value) return
  form.value.feeName = inputValue(event)
  invalidatePreview()
}

function setCategory(event: unknown): void {
  if (locked.value) return
  form.value.category = categoryOptions.value[Number(pickerValue(event))]?.key ?? 'platform'
  invalidatePreview()
}

function setReason(event: unknown): void {
  if (locked.value) return
  form.value.reason = inputValue(event)
  invalidatePreview()
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
    const page = asObject<{ items: FeeRuleSaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/fee-rules'), {
        data_identity: identity.value,
        channel: channel.value,
      }),
    )
    rules.value = asRows<FeeRuleSaved>(page?.items)
    nextCursor.value = page?.next_cursor ?? null
  })
  error.value = message
}

async function loadMore(): Promise<void> {
  const cursor = nextCursor.value
  if (cursor === null) return
  const message = await perform(async () => {
    const page = asObject<{ items: FeeRuleSaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/fee-rules'), {
        data_identity: identity.value,
        channel: channel.value,
        before: cursor,
      }),
    )
    const incoming = asRows<FeeRuleSaved>(page?.items)
    rules.value = [
      ...rules.value,
      ...incoming.filter((item) => !rules.value.some((old) => old.id === item.id)),
    ]
    nextCursor.value = page?.next_cursor ?? null
  })
  error.value = message
}

function resetDraft(): void {
  ruleRecord.value = null
  form.value = emptyDraft()
  invalidatePreview()
}

/** 打开规则：回读服务端记录并用正文替换表单，同时作废旧预览。 */
async function openRule(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<FeeRuleSaved>(await apiGet(shopPath(`/fee-rules/${id}`)))
    if (value === null) throw new Error('规则响应无法读取，请刷新重试。')
    ruleRecord.value = value
    identity.value = value.data_identity
    channel.value = value.channel
    form.value = {
      feeName: value.content?.fee_name ?? '',
      category: value.content?.category ?? 'platform',
      reason: value.content?.reason ?? '',
    }
    invalidatePreview()
  })
  if (message === '') success('费用映射规则已回读。')
  else error.value = message
}

/** 预览：先做必填校验，必填留空不提交。 */
async function preview(): Promise<void> {
  const message = await perform(async () => {
    if (form.value.feeName.trim() === '') throw new Error('请填写账单费用名称。')
    if (form.value.feeName.trim().length > 120) throw new Error('账单费用名称最多 120 字。')
    if (form.value.reason.trim() === '') throw new Error('请填写分类与修订依据。')
    if (form.value.reason.trim().length > 500) throw new Error('分类与修订依据最多 500 字。')
    const value = asObject<FeeRulePreview>(
      await apiPost(shopPath('/fee-rules/preview'), {
        scope: scopePayload(),
        rule_id: ruleRecord.value?.id ?? null,
        version: ruleRecord.value?.version ?? 0,
        content: {
          fee_name: form.value.feeName.trim(),
          category: form.value.category,
          reason: form.value.reason.trim(),
        },
      }),
    )
    if (value === null) throw new Error('预览响应无法读取，请刷新后重试。')
    previewResult.value = value
    confirmed.value = false
    // 新预览代表新的保存意图：释放旧的幂等键与待确认状态。
    pending.value = false
    pendingKey.value = null
  })
  if (message === '') success('已生成映射影响预览，请核对受影响账单行后再保存。')
  else error.value = message
}

/** 保存：只能保存当前预览指纹；结果未知时沿用同一请求号回读或重发核对，不推断成功。 */
async function save(): Promise<void> {
  if (pending.value && ruleRecord.value !== null) {
    // 已有记录：直接回读服务端版本。
    await openRule(ruleRecord.value.id)
    return
  }
  const previewValue = previewResult.value
  if (previewValue === null) {
    error.value = '保存需要当前来源的预览指纹，请先执行“预览映射变化”。'
    return
  }
  // 新建记录且上次写入结果未知时，沿用同一 request_id 重发，由服务端幂等判定，不产生第二条规则。
  const key = pendingKey.value ?? newRequestId()
  pendingKey.value = key
  await writeAction(async () => {
    const value = asObject<FeeRuleSaved>(
      await apiPost(shopPath('/fee-rules'), {
        scope: scopePayload(),
        rule_id: ruleRecord.value?.id ?? null,
        version: ruleRecord.value?.version ?? 0,
        content: previewValue.proposed,
        preview_hash: previewValue.preview_hash,
        request_id: key,
        confirm: true,
      }),
    )
    if (value === null) throw new Error('保存响应无法读取，请到规则列表回读核对。')
    pending.value = false
    pendingKey.value = null
    ruleRecord.value = value
    previewResult.value = null
    confirmed.value = false
    await load()
  }, '费用映射规则已保存；账单分类须按当前规则重新核对。', '规则列表')
}

async function control(action: 'withdraw' | 'clear'): Promise<void> {
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
    await load()
  }, '规则状态已更新。', '规则列表')
}
</script>
