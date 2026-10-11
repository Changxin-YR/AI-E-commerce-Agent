<template>
  <PageShell
    title="经营规则与授权"
    subtitle="按店铺、渠道和数据身份使用规则。有效规则的阈值优先，巡检与计划须绑定当前版本。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <FactLine label="所属店铺" :value="shopName" />
    <FactLine label="业务时区" :value="zone" />

    <text class="section-title">规则范围</text>
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
    <view class="row">
      <ActionButton label="读取当前规则与历史" variant="primary" :disabled="busy" @tap="load" />
    </view>
    <text v-if="uncertain" class="warn">请先回读最新规则，核对上次操作结果后再修改。</text>
    <FactLine label="当前版本" :value="current === null ? '未知' : `#${current.version} · ${current.active === true ? '已启用' : '默认 / 已停用'}`" />
    <FactLine v-if="current" label="规则来源版本" :value="current.restored_from === null || current.restored_from === undefined ? '未恢复历史版本' : `恢复自 #${current.restored_from}`" />
    <FactLine v-if="current" label="自动化方式" :value="current.values.automation === 'manual_only' ? '仅人工执行（不外发）' : factText(current.values.automation)" />

    <text class="section-title">阈值、预算与依据</text>
    <view class="field">
      <text class="field__label">库存有效小时（1–720）</text>
      <input class="field__input" :value="form.maxAgeHours" :disabled="busy || uncertain" @input="form.maxAgeHours = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">最低销量（1–1000000）</text>
      <input class="field__input" :value="form.minQuantity" :disabled="busy || uncertain" @input="form.minQuantity = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">低毛利率上限 %</text>
      <input class="field__input" :value="form.maxMarginPercent" :disabled="busy || uncertain" @input="form.maxMarginPercent = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">广告日预算（留空表示未设置）</text>
      <input class="field__input" :value="form.advertisingBudget" :disabled="busy || uncertain" @input="form.advertisingBudget = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">预算币种</text>
      <input class="field__input" :value="form.currency" :disabled="busy || uncertain" @input="form.currency = inputValue($event).toUpperCase()" />
    </view>
    <view class="field">
      <text class="field__label">规则依据（必填）</text>
      <input class="field__input" :value="form.basis" :disabled="busy || uncertain" @input="form.basis = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">目标站点</text>
      <input class="field__input" :value="form.targetSite" :disabled="busy || uncertain" @input="form.targetSite = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">仓库说明</text>
      <input class="field__input" :value="form.warehouse" :disabled="busy || uncertain" @input="form.warehouse = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">物流说明</text>
      <input class="field__input" :value="form.logistics" :disabled="busy || uncertain" @input="form.logistics = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">品牌表达</text>
      <input class="field__input" :value="form.brandVoice" :disabled="busy || uncertain" @input="form.brandVoice = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">客服措辞</text>
      <input class="field__input" :value="form.supportWording" :disabled="busy || uncertain" @input="form.supportWording = inputValue($event)" />
    </view>
    <view class="card" @tap="confirmed = !confirmed">
      <text class="chip" :class="{ 'chip--active': confirmed }">
        {{ confirmed ? '已核对' : '未核对' }} · 已核对规则作用范围、阈值、预算与依据
      </text>
    </view>
    <view class="row">
      <ActionButton label="保存并启用规则" variant="primary" :disabled="busy || uncertain || !confirmed" @tap="change('save')" />
      <ActionButton label="停用规则" :disabled="busy || uncertain || current === null" @tap="change('revoke')" />
      <ActionButton label="重置默认口径" :disabled="busy || uncertain || current === null" @tap="change('reset')" />
    </view>

    <text class="section-title">内部运营授权</text>
    <text class="hint">
      在 AI 运营的每日候选预览中创建有限次数授权，核对范围、期限和消耗记录，并可撤销授权或撤回消耗产生的候选。
    </text>
    <view class="row">
      <ActionButton label="刷新授权列表" :disabled="busy" @tap="loadAuthorizations" />
      <ActionButton label="管理 AI 运营授权" :disabled="busy" @tap="openPage('/pages/agent/index')" />
    </view>
    <view v-if="authorizations.length === 0 && !busy" class="card">
      <text class="hint">当前店铺暂无内部运营授权。可在 AI 运营的候选预览中创建。</text>
    </view>
    <view v-for="grant in authorizations" :key="grant.id" class="card">
      <text class="card__title">授权 #{{ grant.id }} · {{ labelOf(authorizationStatuses, grant.status) }}</text>
      <FactLine label="技能 / 风险等级" :value="`${labelOf(agentLabels, grant.skill)} / ${grant.risk}`" />
      <FactLine label="来源执行" :value="grant.origin_execution_id" />
      <FactLine label="来源修订 / 候选数量" :value="`${grant.source_revision} / ${grant.candidate_count}`" />
      <FactLine label="已用 / 上限" :value="`${grant.used_count} / ${grant.max_uses}`" />
      <FactLine label="到期时间" :value="grant.expires_at" :zone="zone" />
      <FactLine label="来源有效至" :value="grant.source_valid_until" :zone="zone" />
      <FactLine v-if="grant.revoked_at" label="撤销时间" :value="grant.revoked_at" :zone="zone" />
      <view class="row">
        <ActionButton label="回读授权" :disabled="busy" @tap="openGrant(grant.id)" />
        <ActionButton label="撤销授权" :disabled="busy" @tap="revokeGrant(grant)" />
      </view>
    </view>

    <template v-if="selectedGrant !== null">
      <text class="section-title">授权 #{{ selectedGrant.id }} 的范围与消耗</text>
      <FactLine label="规则范围" :value="`${labelOf(importIdentities, selectedGrant.scope.data_identity)} / ${labelOf(importChannels, selectedGrant.scope.channel)}`" />
      <FactLine label="分析范围 / 意图" :value="`${selectedGrant.scope.intent} · ${selectedGrant.scope.start_at} 至 ${selectedGrant.scope.end_at}`" :zone="zone" />
      <FactLine label="成本口径 / 规则版本" :value="`${selectedGrant.scope.cost_mode} / ${selectedGrant.scope.rule_revision_id}`" />
      <FactLine label="库存有效小时 / 最低销量 / 毛利率上限" :value="`${selectedGrant.scope.max_age_hours} / ${selectedGrant.scope.min_quantity} / ${selectedGrant.scope.max_margin_percent}%`" />
      <view v-for="use in selectedGrant.uses ?? []" :key="use.id" class="card">
        <text class="card__title">消耗 #{{ use.id }} · 执行 {{ use.execution_id }}</text>
        <text class="hint">{{ businessTimeText(use.created_at, zone) }} · 运行 {{ use.operation_run_id }} · 复用 {{ use.reused_count }} 次</text>
        <FactLine label="候选变更数" :value="(use.changes ?? []).length" />
        <FactLine label="撤回时间" :value="use.reverted_at" :zone="zone" />
        <ActionButton v-if="use.reverted_at === null || use.reverted_at === undefined" label="撤回本次消耗产生的候选" :disabled="busy" @tap="revertUse(selectedGrant, use.id)" />
      </view>
      <view class="row">
        <ActionButton label="关闭授权详情" :disabled="busy" @tap="selectedGrant = null" />
      </view>
    </template>

    <text class="section-title">规则版本历史</text>
    <view v-if="history.length === 0 && !busy" class="card">
      <text class="hint">当前范围暂无历史版本，说明尚未保存过经营规则。</text>
    </view>
    <view v-for="item in history" :key="item.version" class="card" @tap="openVersion(item.version)">
      <text class="card__title">规则 #{{ item.version }} · {{ item.active === true ? '有效' : '默认 / 停用' }}</text>
      <text class="hint">{{ labelOf(ruleActions, item.action) }} · 前一版本 {{ item.previous_version }} · {{ businessTimeText(item.created_at, zone) }}</text>
      <FactLine label="依据" :value="item.values.basis" />
    </view>
    <ActionButton v-if="nextCursor !== null" label="更早版本" :disabled="busy" @tap="loadOlderHistory" />

    <template v-if="selected !== null">
      <text class="section-title">规则 #{{ selected.version }} 详情</text>
      <FactLine label="范围" :value="`${labelOf(importIdentities, selected.data_identity)} / ${labelOf(importChannels, selected.channel)}`" />
      <FactLine label="前一版本" :value="selected.previous_version" />
      <FactLine label="恢复来源版本" :value="selected.restored_from" />
      <FactLine label="生效时间" :value="selected.created_at" :zone="zone" />
      <FactLine v-for="field in valueFields" :key="field.key" :label="field.label" :value="versionValue(selected, field.key)" />
      <ActionButton label="恢复历史规则为新版本" variant="primary" :disabled="busy || uncertain || !confirmed" @tap="restore(selected.version)" />
      <ActionButton label="关闭版本详情" :disabled="busy" @tap="selected = null" />
      <text class="hint">经营规则提供本地检查口径；执行权限由对应业务审批或授权决定。</text>
    </template>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 经营规则与授权：规则范围、阈值与预算、依据，版本的保存/停用/重置/恢复，
 * 以及内部运营授权（propose_tasks R1）的回读、撤销与消耗撤回。
 * 接口（均来自 contracts/ui-contract.json 的 r2.rules）：
 *   GET  /api/shops/{shop_id}/business-rules?channel&data_identity
 *   POST /api/shops/{shop_id}/business-rules
 *   GET  /api/shops/{shop_id}/business-rules/history
 *   GET  /api/shops/{shop_id}/business-rules/{version}
 *   GET  /api/shops/{shop_id}/authorizations
 *   GET  /api/shops/{shop_id}/authorizations/{grant_id}
 *   POST /api/shops/{shop_id}/authorizations/{grant_id}/revoke
 *   POST /api/shops/{shop_id}/authorizations/{grant_id}/uses/{use_id}/revert
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import ActionButton from '../../ui/ActionButton.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import { ApiError, apiGet, apiPost, asObject, asRows } from '../../core/api'
import { businessTimeText, factText, isDecimalInput, moneyText } from '../../core/format'
import { agentLabels, importChannels, importIdentities, labelOf } from '../../core/labels'
import { openPage } from '../../core/links'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

const ruleActions: Record<string, string> = {
  save: '保存并启用规则',
  revoke: '停用经营规则',
  reset: '重置检查口径',
  restore: '恢复历史规则',
}

const authorizationStatuses: Record<string, string> = {
  active: '当前有效',
  exhausted: '次数已用尽',
  expired: '已过期',
  revoked: '已撤销',
  source_changed: '来源已变化 · 待重核',
  rules_changed: '规则版本已变化 · 待重核',
}

interface RuleNotes {
  target_site: string
  warehouse: string
  logistics: string
  brand_voice: string
  support_wording: string
}

interface RuleValues {
  max_age_hours: number
  min_quantity: number
  max_margin_percent: string
  advertising_daily_budget?: string | null
  currency: string
  notes: RuleNotes
  basis: string
  automation: string
}

interface RuleRevision {
  version: number
  previous_version: number
  restored_from?: number | null
  shop_id: number
  channel: string
  data_identity: string
  action: string
  active: boolean
  values: RuleValues
  created_at?: string | null
}

interface OperationScope {
  cost_mode: string
  rule_revision_id: number
  intent: string
  channel: string
  max_age_hours: number
  start_at: string
  end_at: string
  timezone: string
  currency: string
  data_identity: string
  min_quantity: number
  max_margin_percent: string
}

interface AuthorizationUse {
  id: number
  execution_id: number
  operation_run_id: number
  changes: unknown[]
  reused_count: number
  created_at: string
  reverted_at?: string | null
}

interface Authorization {
  id: number
  shop_id: number
  version: number
  origin_execution_id: number
  skill: string
  risk: string
  scope: OperationScope
  source_revision: number
  candidate_count: number
  max_uses: number
  used_count: number
  status: string
  expires_at: string
  source_valid_until?: string | null
  revoked_at?: string | null
  created_at: string
  uses: AuthorizationUse[]
}

interface RuleForm {
  maxAgeHours: string
  minQuantity: string
  maxMarginPercent: string
  advertisingBudget: string
  currency: string
  basis: string
  targetSite: string
  warehouse: string
  logistics: string
  brandVoice: string
  supportWording: string
}

function emptyForm(): RuleForm {
  return {
    maxAgeHours: '24',
    minQuantity: '1',
    maxMarginPercent: '20',
    advertisingBudget: '',
    currency: 'USD',
    basis: '',
    targetSite: '',
    warehouse: '',
    logistics: '',
    brandVoice: '',
    supportWording: '',
  }
}

const valueFields = [
  { key: 'max_age_hours', label: '库存有效小时' },
  { key: 'min_quantity', label: '最低销量' },
  { key: 'max_margin_percent', label: '低毛利率上限 %' },
  { key: 'advertising_daily_budget', label: '广告日预算' },
  { key: 'currency', label: '预算币种' },
  { key: 'basis', label: '规则依据' },
  { key: 'target_site', label: '目标站点' },
  { key: 'warehouse', label: '仓库' },
  { key: 'logistics', label: '物流' },
  { key: 'brand_voice', label: '品牌表达' },
  { key: 'support_wording', label: '客服措辞' },
]

const identity = ref('user_import')
const channel = ref('generic')
const current = ref<RuleRevision | null>(null)
const history = ref<RuleRevision[]>([])
const nextCursor = ref<number | null>(null)
const selected = ref<RuleRevision | null>(null)
const form = ref<RuleForm>(emptyForm())
const confirmed = ref(false)
const uncertain = ref(false)
const authorizations = ref<Authorization[]>([])
const selectedGrant = ref<Authorization | null>(null)
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
  if (unknown) uncertain.value = true
}

function setIdentity(event: unknown): void {
  identity.value = identityOptions.value[Number(pickerValue(event))]?.key ?? 'user_import'
  uncertain.value = false
}

function setChannel(event: unknown): void {
  channel.value = channelOptions.value[Number(pickerValue(event))]?.key ?? 'generic'
  uncertain.value = false
}

function scopeQuery(): Record<string, string> {
  return { channel: channel.value, data_identity: identity.value }
}

/** 版本详情取值：notes 子对象在这里展平，金额保持服务端字符串。 */
function versionValue(revision: RuleRevision, key: string): unknown {
  const values = revision.values
  if (values === undefined || values === null) return null
  const notes = values.notes as unknown as Record<string, unknown>
  if (key in (notes ?? {})) return notes[key]
  const raw = (values as unknown as Record<string, unknown>)[key]
  if (key === 'advertising_daily_budget') return moneyText(raw, values.currency)
  return factText(raw)
}

function applyValues(values: RuleValues): void {
  form.value = {
    maxAgeHours: `${values.max_age_hours}`,
    minQuantity: `${values.min_quantity}`,
    maxMarginPercent: `${values.max_margin_percent}`,
    advertisingBudget: values.advertising_daily_budget === null || values.advertising_daily_budget === undefined
      ? ''
      : `${values.advertising_daily_budget}`,
    currency: values.currency,
    basis: values.basis,
    targetSite: values.notes?.target_site ?? '',
    warehouse: values.notes?.warehouse ?? '',
    logistics: values.notes?.logistics ?? '',
    brandVoice: values.notes?.brand_voice ?? '',
    supportWording: values.notes?.support_wording ?? '',
  }
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  await load()
  await loadAuthorizations()
})

async function load(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    const value = asObject<RuleRevision>(await apiGet(shopPath('/business-rules'), scopeQuery()))
    current.value = value
    if (value !== null) {
      applyValues(value.values)
      uncertain.value = false
    }
    selected.value = null
    const page = asObject<{ items?: RuleRevision[]; next_before_version?: number | null } | RuleRevision[]>(
      await apiGet(shopPath('/business-rules/history'), { ...scopeQuery(), before: undefined }),
    )
    if (Array.isArray(page)) {
      history.value = asRows<RuleRevision>(page)
      nextCursor.value = history.value.length > 0 ? history.value[history.value.length - 1].version : null
    } else {
      history.value = asRows<RuleRevision>(page?.items)
      nextCursor.value = page?.next_before_version ?? null
    }
    confirmed.value = false
  })
  error.value = message
}

async function loadOlderHistory(): Promise<void> {
  const cursor = nextCursor.value
  if (cursor === null) return
  const message = await perform(async () => {
    const value = await apiGet<RuleRevision[] | { items?: RuleRevision[]; next_before_version?: number | null }>(
      shopPath('/business-rules/history'),
      { ...scopeQuery(), before: cursor },
    )
    const incoming = Array.isArray(value) ? asRows<RuleRevision>(value) : asRows<RuleRevision>(value?.items)
    history.value = [
      ...history.value,
      ...incoming.filter((item) => !history.value.some((old) => old.version === item.version)),
    ]
    nextCursor.value = Array.isArray(value)
      ? (incoming.length > 0 ? incoming[incoming.length - 1].version : null)
      : value?.next_before_version ?? null
  })
  error.value = message
}

async function openVersion(version: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<RuleRevision>(
      await apiGet(shopPath(`/business-rules/${version}`), scopeQuery()),
    )
    if (value === null) throw new Error('版本响应无法读取，请刷新重试。')
    selected.value = value
  })
  error.value = message
}

/** 保存 / 停用 / 重置 / 恢复：同一接口，按 action 决定 payload。 */
async function change(action: 'save' | 'revoke' | 'reset'): Promise<void> {
  const expected = current.value?.version ?? 0
  const modal = await Taro.showModal({
    title: ruleActions[action],
    content: action === 'save'
      ? `保存后生成新版本（当前版本 #${expected}），巡检与计划需读取当前规则。`
      : `此操作会生成新版本，后续巡检需读取当前规则。`,
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const body: Record<string, unknown> = {
      channel: channel.value,
      data_identity: identity.value,
      expected_version: expected,
      action,
    }
    if (action === 'save') body.values = valuesPayload()
    const value = asObject<RuleRevision>(await apiPost(shopPath('/business-rules'), body))
    if (value === null) throw new Error('保存响应无法读取，请回读当前规则核对。')
    current.value = value
    applyValues(value.values)
    await load()
  }, '经营规则已更新。', '当前规则')
}

async function restore(version: number): Promise<void> {
  const expected = current.value?.version ?? 0
  const modal = await Taro.showModal({
    title: ruleActions.restore,
    content: `将历史版本 #${version} 作为新的有效规则，后续巡检需重新读取。`,
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<RuleRevision>(
      await apiPost(shopPath('/business-rules'), {
        channel: channel.value,
        data_identity: identity.value,
        expected_version: expected,
        action: 'restore',
        restore_version: version,
      }),
    )
    if (value === null) throw new Error('恢复响应无法读取，请回读当前规则核对。')
    current.value = value
    applyValues(value.values)
    await load()
  }, '历史规则已恢复为新版本。', '当前规则')
}

function integerInRange(value: string, min: number, max: number): boolean {
  return /^\d+$/.test(value.trim()) && Number(value) >= min && Number(value) <= max
}

function valuesPayload(): RuleValues {
  if (!integerInRange(form.value.maxAgeHours, 1, 720)) throw new Error('库存有效小时须为 1–720 的整数。')
  if (!integerInRange(form.value.minQuantity, 1, 1000000)) throw new Error('最低销量须为 1–1000000 的整数。')
  if (!isDecimalInput(form.value.maxMarginPercent)) throw new Error('低毛利率上限须为数字。')
  const budget = form.value.advertisingBudget.trim()
  if (budget !== '' && (!isDecimalInput(budget) || budget.startsWith('-'))) {
    throw new Error('广告日预算须为非负数字，留空表示未设置。')
  }
  if (form.value.currency.trim() === '') throw new Error('请填写预算币种。')
  if (form.value.basis.trim() === '') throw new Error('请填写规则依据。')
  return {
    max_age_hours: Number(form.value.maxAgeHours.trim()),
    min_quantity: Number(form.value.minQuantity.trim()),
    max_margin_percent: form.value.maxMarginPercent.trim(),
    advertising_daily_budget: budget === '' ? null : budget,
    currency: form.value.currency.trim().toUpperCase(),
    notes: {
      target_site: form.value.targetSite.trim(),
      warehouse: form.value.warehouse.trim(),
      logistics: form.value.logistics.trim(),
      brand_voice: form.value.brandVoice.trim(),
      support_wording: form.value.supportWording.trim(),
    },
    basis: form.value.basis.trim(),
    automation: 'manual_only',
  }
}

async function loadAuthorizations(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    const value = await apiGet<Authorization[] | { items?: Authorization[] }>(shopPath('/authorizations'))
    authorizations.value = Array.isArray(value) ? asRows<Authorization>(value) : asRows<Authorization>(value?.items)
  })
  error.value = message
}

async function openGrant(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<Authorization>(await apiGet(shopPath(`/authorizations/${id}`)))
    if (value === null) throw new Error('授权响应无法读取，请刷新重试。')
    selectedGrant.value = value
  })
  error.value = message
}

async function revokeGrant(grant: Authorization): Promise<void> {
  const modal = await Taro.showModal({
    title: `撤销授权 #${grant.id}`,
    content: '撤销后该授权不可再用于保存候选；已产生的候选需按业务页面核对。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<Authorization>(
      await apiPost(shopPath(`/authorizations/${grant.id}/revoke`), { version: grant.version }),
    )
    if (value !== null) selectedGrant.value = value
    await loadAuthorizations()
  }, '授权已撤销。', '授权列表')
}

async function revertUse(grant: Authorization, useId: number): Promise<void> {
  const modal = await Taro.showModal({
    title: `撤回消耗 #${useId}`,
    content: '撤回该次消耗产生的候选；已执行的其他记录不受影响。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    await apiPost(shopPath(`/authorizations/${grant.id}/uses/${useId}/revert`))
    await openGrant(grant.id)
    await loadAuthorizations()
  }, '消耗已撤回。', '授权详情')
}
</script>
