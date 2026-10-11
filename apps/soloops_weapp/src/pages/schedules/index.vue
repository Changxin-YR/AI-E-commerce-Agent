<template>
  <PageShell
    title="定时运营与通知"
    subtitle="计划按业务时区与当地时刻运行；免打扰只推迟应用内通知，执行记录仍可回查。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <FactLine label="所属店铺" :value="shopName" />
    <FactLine label="业务时区" :value="zone" />

    <text class="section-title">自动调度配置</text>
    <FactLine
      label="调度进程"
      :value="status === null
        ? '未知'
        : (status.worker_enabled === true ? '已启用 · 服务运行时约每 30 秒扫描' : '当前服务未启用')"
    />
    <text class="hint">
      API 服务须保持运行。恢复后只尝试最近一期，超过 24 小时记为错过；暂停期间不补跑。
      自动调度配置与历史周期都不能单独证明调度进程正在运行。
    </text>
    <FactLine
      v-if="status !== null && status.latest_timer !== null"
      label="最近周期记录"
      :value="`#${status.latest_timer.id} · 计划 ${status.latest_timer.schedule_id} · ${labelOf(scheduleLabels, status.latest_timer.status)}`"
    />
    <text v-else class="hint">尚无自动周期记录。周期记录用于回查实际运行，其时间不代表服务当前在线。</text>

    <view class="row">
      <ActionButton label="新建计划" variant="primary" :disabled="busy" @tap="startCreate" />
      <ActionButton label="刷新计划与通知" :disabled="busy" @tap="load" />
      <ActionButton v-if="pendingKey !== null" label="核对同次操作" :disabled="busy" @tap="reconcilePending" />
    </view>
    <text v-if="pendingKey !== null" class="warn">上次操作结果待确认，请核对同次请求。</text>

    <text class="section-title">运行计划</text>
    <view v-if="schedules.length === 0 && !busy" class="card">
      <text class="hint">当前店铺尚无运行计划。新建后可立即执行一次以核对范围。</text>
    </view>
    <view v-for="plan in schedules" :key="plan.id" class="card">
      <text class="card__title">
        #{{ plan.id }} · v{{ plan.version }} · 下次 {{ plan.next_run_at === null || plan.next_run_at === undefined ? '未安排' : businessTimeText(plan.next_run_at, plan.config.timezone) }}
      </text>
      <text class="hint">
        {{ factText(plan.config.name) }} · {{ labelOf(scheduleLabels, plan.status) }} ·
        {{ labelOf(frequencies, plan.config.frequency) }} {{ plan.config.local_time }}（{{ plan.config.timezone }}）
      </text>
      <text class="hint">
        {{ plan.config.task === 'report' ? '经营报表' : '运营巡检' }} ·
        {{ labelOf(importIdentities, plan.config.data_identity) }} / {{ labelOf(importChannels, plan.config.channel) }} ·
        规则版本 {{ plan.config.rule_revision_id }}
      </text>
      <view class="row">
        <ActionButton label="修改计划" :disabled="busy" @tap="startEdit(plan)" />
        <ActionButton label="立即执行一次" :disabled="busy" @tap="runCheck(plan)" />
        <ActionButton v-if="plan.status !== 'paused'" label="暂停" :disabled="busy" @tap="control(plan, 'pause')" />
        <ActionButton v-if="plan.status === 'paused'" label="恢复" :disabled="busy" @tap="control(plan, 'resume')" />
        <ActionButton v-if="plan.status !== 'revoked'" label="撤销" :disabled="busy" @tap="control(plan, 'revoke')" />
        <ActionButton label="打开计划详情" :disabled="busy" @tap="startEdit(plan)" />
      </view>
    </view>

    <template v-if="editing">
      <text class="section-title">{{ current === null ? '新建计划' : `修改计划 #${current.id}` }}</text>
      <text v-if="current !== null" class="hint">请回读当前计划，核对上次修改结果。</text>
      <view class="row">
        <ActionButton v-if="current !== null" label="回读计划并替换表单" :disabled="busy" @tap="reloadPlan(current.id)" />
        <ActionButton label="取消编辑" :disabled="busy" @tap="closeEditor" />
      </view>
      <view class="field">
        <text class="field__label">计划名称</text>
        <input class="field__input" :value="form.name" :disabled="busy" @input="form.name = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">计划内容</text>
        <picker mode="selector" :range="taskOptions" range-key="label" :value="taskIndex" @change="form.task = taskOptions[Number(pickerValue($event))]?.key ?? 'operations'">
          <view class="field__picker">{{ form.task === 'operations' ? '运营巡检 · 候选逐次审批' : '经营报表 · 按期保存摘要' }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">运行时区（IANA）</text>
        <input class="field__input" :value="form.timezone" :disabled="busy" @input="form.timezone = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">周期</text>
        <picker mode="selector" :range="frequencyOptions" range-key="label" :value="frequencyIndex" @change="form.frequency = frequencyOptions[Number(pickerValue($event))]?.key ?? 'daily'">
          <view class="field__picker">{{ labelOf(frequencies, form.frequency) }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">当地运行时间 HH:mm</text>
        <picker mode="time" :value="form.localTime" @change="form.localTime = pickerValue($event)">
          <view class="field__picker">{{ form.localTime }}</view>
        </picker>
      </view>
      <view v-if="form.frequency === 'weekly'" class="field">
        <text class="field__label">星期</text>
        <picker mode="selector" :range="weekdayOptions" range-key="label" :value="weekdayIndex" @change="form.weekday = weekdayOptions[Number(pickerValue($event))]?.key ?? '0'">
          <view class="field__picker">{{ weekdayLabel }}</view>
        </picker>
      </view>
      <view v-if="form.frequency === 'monthly'" class="field">
        <text class="field__label">每月日期（1–28）</text>
        <input class="field__input" type="number" :value="form.monthDay" :disabled="busy" @input="form.monthDay = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">订单回看天数（每一天为 24 小时）</text>
        <input class="field__input" type="number" :value="form.lookbackDays" :disabled="busy" @input="form.lookbackDays = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">数据身份</text>
        <picker mode="selector" :range="identityOptions" range-key="label" :value="identityIndex" @change="form.dataIdentity = identityOptions[Number(pickerValue($event))]?.key ?? 'user_import'">
          <view class="field__picker">{{ labelOf(importIdentities, form.dataIdentity) }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">渠道</text>
        <picker mode="selector" :range="channelOptions" range-key="label" :value="channelIndex" @change="form.channel = channelOptions[Number(pickerValue($event))]?.key ?? 'generic'">
          <view class="field__picker">{{ labelOf(importChannels, form.channel) }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="field__label">基础币种</text>
        <input class="field__input" :value="form.currency" :disabled="busy" @input="form.currency = inputValue($event).toUpperCase()" />
      </view>
      <text v-if="form.task === 'report'" class="hint">
        日报汇总前一自然日，周报每周一汇总上个完整周，月报每月 1 日汇总上个自然月，并对比上一期。覆盖全部导入渠道。
      </text>
      <template v-if="form.task === 'report'">
        <text class="hint">报表币种：不选时按全部币种分别统计</text>
        <view class="row">
          <text
            v-for="item in currencyChoices"
            :key="item"
            class="chip"
            :class="{ 'chip--active': form.reportCurrencies.includes(item) }"
            @tap="toggleReportCurrency(item)"
          >
            {{ item }}
          </text>
        </view>
      </template>
      <view class="card">
        <text class="card__title">绑定经营规则</text>
        <text class="hint">
          {{ ruleRevision === null
            ? (current === null
              ? '尚未读取当前经营规则；保存时绑定版本 0（默认口径）。'
              : `尚未读取当前经营规则；当前计划绑定版本 ${current.config.rule_revision_id}，未读取时保存后按默认口径。`)
            : `#${ruleRevision.version} · ${ruleRevision.active === true ? '使用有效阈值' : '可设置本次阈值'}` }}
        </text>
        <ActionButton label="读取当前经营规则" :disabled="busy" @tap="loadRule" />
      </view>
      <view class="field">
        <text class="field__label">库存有效小时（1–720）</text>
        <input class="field__input" :value="form.maxAgeHours" :disabled="busy" @input="form.maxAgeHours = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">最低销量（1–1000000）</text>
        <input class="field__input" :value="form.minQuantity" :disabled="busy" @input="form.minQuantity = inputValue($event)" />
      </view>
      <view class="field">
        <text class="field__label">低毛利率上限 %</text>
        <input class="field__input" :value="form.maxMarginPercent" :disabled="busy" @input="form.maxMarginPercent = inputValue($event)" />
      </view>
      <view class="card" @tap="form.quiet = !form.quiet">
        <text class="chip" :class="{ 'chip--active': form.quiet }">
          {{ form.quiet ? '已开启' : '未开启' }} · 应用内通知免打扰
        </text>
      </view>
      <template v-if="form.quiet">
        <view class="field">
          <text class="field__label">免打扰开始小时（0–23）</text>
          <input class="field__input" type="number" :value="form.quietStart" :disabled="busy" @input="form.quietStart = inputValue($event)" />
        </view>
        <view class="field">
          <text class="field__label">免打扰结束小时（0–23）</text>
          <input class="field__input" type="number" :value="form.quietEnd" :disabled="busy" @input="form.quietEnd = inputValue($event)" />
        </view>
        <text class="hint">夏令时重复时刻只运行第一次，不存在的时刻跳过。免打扰推迟通知，执行记录仍可回查。</text>
      </template>
      <view class="card" @tap="confirmed = !confirmed">
        <text class="chip" :class="{ 'chip--active': confirmed }">
          {{ confirmed ? '已核对' : '未核对' }} · 已核对计划范围、当地运行时间、规则与应用内通知
        </text>
      </view>
      <ActionButton
        :label="pendingKey === null ? '保存计划' : '核对同次创建'"
        variant="primary"
        block
        :disabled="busy || !confirmed"
        @tap="savePlan"
      />
    </template>

    <text class="section-title">应用内通知与运行历史</text>
    <view class="card" @tap="toggleUnreadOnly">
      <text class="chip" :class="{ 'chip--active': unreadOnly }">
        {{ unreadOnly ? '已开启' : '未开启' }} · 只看已到通知时间的未读记录
      </text>
    </view>
    <view v-if="visibleHistory.length === 0 && !busy" class="card">
      <text class="hint">当前筛选没有周期记录。计划执行后会在本列表出现。</text>
    </view>
    <view v-for="item in visibleHistory" :key="item.id" class="card">
      <text class="card__title">周期 #{{ item.id }} · {{ labelOf(scheduleLabels, item.status) }}</text>
      <text class="hint">
        计划 #{{ item.schedule_id }} v{{ item.schedule_version }} · {{ businessTimeText(item.scheduled_at, planZone(item.schedule_id)) }}
      </text>
      <FactLine label="触发方式" :value="item.trigger === 'manual' ? '手动' : '自动周期'" />
      <FactLine label="创建时间" :value="item.created_at" :zone="planZone(item.schedule_id)" />
      <FactLine label="通知时间" :value="item.notify_at" :zone="planZone(item.schedule_id)" />
      <FactLine label="已读时间" :value="item.read_at" :zone="planZone(item.schedule_id)" />
      <FactLine label="合并周期起点" :value="item.coalesced_from" :zone="planZone(item.schedule_id)" />
      <text v-if="item.reason !== ''" class="warn">运行说明：{{ scheduleReasons[item.reason] ?? item.reason }}</text>
      <view class="row">
        <ActionButton v-if="item.read_at === null || item.read_at === undefined" label="标记已读" :disabled="busy" @tap="markRead(item.id)" />
        <ActionButton
          v-if="item.execution_id !== null && item.execution_id !== undefined"
          label="查看运行进度与审批"
          :disabled="busy"
          @tap="openPage('/pages/agent/index', { run: `${item.execution_id}` })"
        />
        <ActionButton
          v-if="item.report_id !== null && item.report_id !== undefined"
          label="查看报表与依据"
          :disabled="busy"
          @tap="openPage('/pages/overview/index', { report: `${item.report_id}` })"
        />
      </view>
    </view>
    <ActionButton v-if="nextCursor !== null" label="更早记录" :disabled="busy" @tap="loadOlder" />
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 定时运营与通知：计划周期/时区/免打扰/范围、增改与启停撤销、立即运行一次、
 * 通知已读、周期历史与关联页面深链。
 * 接口（均来自 contracts/ui-contract.json 的 r2.schedules）：
 *   GET  /api/shops/{shop_id}/schedules/status
 *   GET  /api/shops/{shop_id}/schedules            POST /api/shops/{shop_id}/schedules
 *   POST /api/shops/{shop_id}/schedules/{schedule_id}          （pause / resume / revoke / edit）
 *   POST /api/shops/{shop_id}/schedules/{schedule_id}/check    （立即执行一次）
 *   GET  /api/shops/{shop_id}/schedules/history
 *   POST /api/shops/{shop_id}/schedules/history/{item_id}/read
 *   GET  /api/shops/{shop_id}/business-rules                    （读取当前规则版本）
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import ActionButton from '../../ui/ActionButton.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import { ApiError, apiGet, apiPost, asObject, asRows, newRequestId } from '../../core/api'
import { businessTimeText, factText, isDecimalInput } from '../../core/format'
import { importChannels, importIdentities, labelOf } from '../../core/labels'
import { openPage, pageQuery } from '../../core/links'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

const scheduleLabels: Record<string, string> = {
  active: '已启用',
  paused: '已暂停',
  revoked: '已撤销',
  waiting_approval: '等待审批',
  succeeded: '已完成',
  blocked: '运行受阻',
  missed: '错过周期',
  ready: '等待继续',
  circuit_open: '读取失败',
  cancelled: '已取消',
}

const scheduleReasons: Record<string, string> = {
  conflict: '经营规则已变化，请编辑计划并重新读取规则。',
  local_check_failed: '运行未完成并已回滚，请核对后恢复。',
  range_too_large: '数据超过上限，请缩小范围。',
  too_many_findings: '候选过多，请缩小范围。',
  invalid_local_date: '报告日期起点在所选时区不存在。',
}

const frequencies: Record<string, string> = {
  daily: '每天',
  weekly: '每周',
  monthly: '每月',
}

const weekdayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

interface ScheduleConfig {
  name: string
  task: string
  report_currencies: string[]
  timezone: string
  frequency: string
  local_time: string
  weekday: number
  month_day: number
  lookback_days: number
  channel: string
  data_identity: string
  currency: string
  rule_revision_id: number
  max_age_hours: number
  min_quantity: number
  max_margin_percent: string
  quiet_start?: number | null
  quiet_end?: number | null
}

interface ScheduleOutput {
  id: number
  shop_id: number
  status: string
  version: number
  config: ScheduleConfig
  next_run_at?: string | null
  created_at: string
}

interface OccurrenceOutput {
  id: number
  shop_id: number
  schedule_id: number
  schedule_version: number
  trigger: string
  scheduled_at: string
  coalesced_from?: string | null
  execution_id?: number | null
  task: string
  report_id?: number | null
  status: string
  reason: string
  notify_at: string
  read_at?: string | null
  created_at: string
}

interface ScheduleStatus {
  worker_enabled: boolean
  latest_timer: OccurrenceOutput | null
}

interface RuleRevision {
  version: number
  active: boolean
  values?: { max_age_hours?: number; min_quantity?: number; max_margin_percent?: string }
}

interface ScheduleForm {
  name: string
  task: string
  timezone: string
  frequency: string
  localTime: string
  weekday: string
  monthDay: string
  lookbackDays: string
  dataIdentity: string
  channel: string
  currency: string
  reportCurrencies: string[]
  maxAgeHours: string
  minQuantity: string
  maxMarginPercent: string
  quiet: boolean
  quietStart: string
  quietEnd: string
}

function emptyForm(): ScheduleForm {
  return {
    name: '每日运营检查',
    task: 'operations',
    timezone: shopTimezone(),
    frequency: 'daily',
    localTime: '09:00',
    weekday: '0',
    monthDay: '1',
    lookbackDays: '7',
    dataIdentity: 'user_import',
    channel: 'generic',
    currency: 'USD',
    reportCurrencies: [],
    maxAgeHours: '24',
    minQuantity: '1',
    maxMarginPercent: '20',
    quiet: false,
    quietStart: '22',
    quietEnd: '8',
  }
}

const currencyChoices = ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']

const status = ref<ScheduleStatus | null>(null)
const schedules = ref<ScheduleOutput[]>([])
const history = ref<OccurrenceOutput[]>([])
const nextCursor = ref<number | null>(null)
const unreadOnly = ref(false)
const editing = ref(false)
const current = ref<ScheduleOutput | null>(null)
const form = ref<ScheduleForm>(emptyForm())
const ruleRevision = ref<RuleRevision | null>(null)
const confirmed = ref(false)
const pendingKey = ref<string | null>(null)
const pendingAction = ref<'create' | number | null>(null)
const busy = ref(false)
const error = ref('')
const successText = ref('')
const ready = ref(false)

const zone = computed(() => shopTimezone())
const shopName = computed(() => state.shops.find((shop) => shop.id === state.shopId)?.name ?? '未知')
const taskOptions = [{ key: 'operations', label: '运营巡检 · 候选逐次审批' }, { key: 'report', label: '经营报表 · 按期保存摘要' }]
const frequencyOptions = computed(() => Object.entries(frequencies).map(([key, label]) => ({ key, label })))
const weekdayOptions = weekdayNames.map((label, index) => ({ key: `${index}`, label }))
const identityOptions = computed(() => Object.entries(importIdentities).map(([key, label]) => ({ key, label })))
const channelOptions = computed(() => Object.entries(importChannels).map(([key, label]) => ({ key, label })))
const taskIndex = computed(() => Math.max(0, taskOptions.findIndex((item) => item.key === form.value.task)))
const frequencyIndex = computed(() => Math.max(0, Object.keys(frequencies).indexOf(form.value.frequency)))
const weekdayIndex = computed(() => Math.max(0, weekdayNames.findIndex((_, index) => `${index}` === form.value.weekday)))
const weekdayLabel = computed(() => weekdayNames[Number(form.value.weekday)] ?? '周一')
const identityIndex = computed(() => Math.max(0, Object.keys(importIdentities).indexOf(form.value.dataIdentity)))
const channelIndex = computed(() => Math.max(0, Object.keys(importChannels).indexOf(form.value.channel)))
const visibleHistory = computed(() => {
  if (!unreadOnly.value) return history.value
  const now = Date.now()
  return history.value.filter((item) => {
    const read = item.read_at === null || item.read_at === undefined
    const notify = Date.parse(item.notify_at)
    return read && (Number.isNaN(notify) || notify <= now)
  })
})

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

function planZone(scheduleId: number): string {
  const plan = schedules.value.find((item) => item.id === scheduleId)
  return plan?.config.timezone ?? zone.value
}

function toggleReportCurrency(currency: string): void {
  form.value.reportCurrencies = form.value.reportCurrencies.includes(currency)
    ? form.value.reportCurrencies.filter((item) => item !== currency)
    : [...form.value.reportCurrencies, currency]
}

function applyConfig(config: ScheduleConfig): void {
  form.value = {
    name: config.name,
    task: config.task,
    timezone: config.timezone,
    frequency: config.frequency,
    localTime: config.local_time,
    weekday: `${config.weekday}`,
    monthDay: `${config.month_day}`,
    lookbackDays: `${config.lookback_days}`,
    dataIdentity: config.data_identity,
    channel: config.channel,
    currency: config.currency,
    reportCurrencies: config.report_currencies ?? [],
    maxAgeHours: `${config.max_age_hours}`,
    minQuantity: `${config.min_quantity}`,
    maxMarginPercent: `${config.max_margin_percent}`,
    quiet: config.quiet_start !== null && config.quiet_start !== undefined && config.quiet_end !== null && config.quiet_end !== undefined,
    quietStart: `${config.quiet_start ?? 22}`,
    quietEnd: `${config.quiet_end ?? 8}`,
  }
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  form.value = { ...emptyForm(), currency: state.shops.find((shop) => shop.id === state.shopId)?.currency ?? 'USD' }
  await load()
  const query = pageQuery()
  const scheduleId = Number(query.schedule ?? '')
  if (Number.isFinite(scheduleId) && scheduleId > 0) await reloadPlan(scheduleId)
  const itemId = Number(query.item ?? '')
  if (Number.isFinite(itemId) && itemId > 0) await markRead(itemId)
})

async function load(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    status.value = asObject<ScheduleStatus>(await apiGet(shopPath('/schedules/status')))
    const list = await apiGet<ScheduleOutput[] | { items?: ScheduleOutput[] }>(shopPath('/schedules'))
    schedules.value = Array.isArray(list) ? asRows<ScheduleOutput>(list) : asRows<ScheduleOutput>(list?.items)
    await loadHistory()
  })
  error.value = message
}

async function loadHistory(): Promise<void> {
  const value = await apiGet<OccurrenceOutput[] | { items?: OccurrenceOutput[]; next_before_id?: number | null }>(
    shopPath('/schedules/history'),
    { unread: unreadOnly.value ? 'true' : undefined },
  )
  if (Array.isArray(value)) {
    history.value = asRows<OccurrenceOutput>(value)
    nextCursor.value = history.value.length > 0 ? history.value[history.value.length - 1].id : null
  } else {
    history.value = asRows<OccurrenceOutput>(value?.items)
    nextCursor.value = value?.next_before_id ?? null
  }
}

/** 切换未读筛选：服务端按 unread 过滤，客户端再按通知时间兜一次。 */
function toggleUnreadOnly(): void {
  if (busy.value) return
  unreadOnly.value = !unreadOnly.value
  void load()
}

async function loadOlder(): Promise<void> {
  const cursor = nextCursor.value
  if (cursor === null) return
  const message = await perform(async () => {
    const value = await apiGet<OccurrenceOutput[] | { items?: OccurrenceOutput[]; next_before_id?: number | null }>(
      shopPath('/schedules/history'),
      { before: cursor, unread: unreadOnly.value ? 'true' : undefined },
    )
    const incoming = Array.isArray(value) ? asRows<OccurrenceOutput>(value) : asRows<OccurrenceOutput>(value?.items)
    history.value = [
      ...history.value,
      ...incoming.filter((item) => !history.value.some((old) => old.id === item.id)),
    ]
    nextCursor.value = Array.isArray(value)
      ? (incoming.length > 0 ? incoming[incoming.length - 1].id : null)
      : value?.next_before_id ?? null
  })
  error.value = message
}

function startCreate(): void {
  current.value = null
  form.value = {
    ...emptyForm(),
    timezone: zone.value,
    currency: state.shops.find((shop) => shop.id === state.shopId)?.currency ?? 'USD',
  }
  ruleRevision.value = null
  confirmed.value = false
  editing.value = true
}

function startEdit(plan: ScheduleOutput): void {
  current.value = plan
  applyConfig(plan.config)
  ruleRevision.value = null
  confirmed.value = false
  editing.value = true
}

function closeEditor(): void {
  editing.value = false
  current.value = null
  confirmed.value = false
}

async function reloadPlan(id: number): Promise<void> {
  const message = await perform(async () => {
    const list = await apiGet<ScheduleOutput[] | { items?: ScheduleOutput[] }>(shopPath('/schedules'))
    const items = Array.isArray(list) ? asRows<ScheduleOutput>(list) : asRows<ScheduleOutput>(list?.items)
    schedules.value = items
    const value = items.find((item) => item.id === id) ?? null
    if (value === null) throw new Error('未找到当前计划，请返回列表核对。')
    current.value = value
    applyConfig(value.config)
    editing.value = true
  })
  error.value = message
}

async function loadRule(): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<RuleRevision>(
      await apiGet(shopPath('/business-rules'), {
        channel: form.value.channel,
        data_identity: form.value.dataIdentity,
      }),
    )
    if (value !== null) {
      ruleRevision.value = value
      form.value.maxAgeHours = `${(value as unknown as { values?: { max_age_hours?: number } }).values?.max_age_hours ?? form.value.maxAgeHours}`
      success('已读取当前经营规则版本，可继续核对阈值。')
    } else {
      throw new Error('当前范围没有有效经营规则，可沿用本次输入阈值。')
    }
  })
  error.value = message
}

function integerInRange(value: string, min: number, max: number): boolean {
  return /^\d+$/.test(value.trim()) && Number(value) >= min && Number(value) <= max
}

function configPayload(): ScheduleConfig {
  if (form.value.name.trim() === '') throw new Error('请填写计划名称。')
  if (form.value.timezone.trim() === '') throw new Error('请填写运行时区。')
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(form.value.localTime.trim())) {
    throw new Error('当地运行时间须为 HH:mm。')
  }
  if (!integerInRange(form.value.lookbackDays, 1, 365)) throw new Error('回看天数须为 1–365 的整数。')
  if (form.value.currency.trim() === '') throw new Error('请填写币种。')
  if (!integerInRange(form.value.maxAgeHours, 1, 720)) throw new Error('库存有效小时须为 1–720 的整数。')
  if (!integerInRange(form.value.minQuantity, 1, 1000000)) throw new Error('最低销量须为 1–1000000 的整数。')
  if (!isDecimalInput(form.value.maxMarginPercent)) throw new Error('低毛利率上限须为数字。')
  const config: ScheduleConfig = {
    name: form.value.name.trim(),
    task: form.value.task,
    report_currencies: form.value.task === 'report' ? form.value.reportCurrencies : [],
    timezone: form.value.timezone.trim(),
    frequency: form.value.frequency,
    local_time: form.value.localTime.trim(),
    weekday: form.value.frequency === 'weekly' ? Number(form.value.weekday) : 0,
    month_day: form.value.frequency === 'monthly' ? Number(form.value.monthDay) : 1,
    lookback_days: Number(form.value.lookbackDays.trim()),
    channel: form.value.channel,
    data_identity: form.value.dataIdentity,
    currency: form.value.currency.trim().toUpperCase(),
    rule_revision_id: ruleRevision.value?.version ?? 0,
    max_age_hours: Number(form.value.maxAgeHours.trim()),
    min_quantity: Number(form.value.minQuantity.trim()),
    max_margin_percent: form.value.maxMarginPercent.trim(),
    quiet_start: null,
    quiet_end: null,
  }
  if (form.value.frequency === 'monthly' && !integerInRange(form.value.monthDay, 1, 28)) {
    throw new Error('每月日期须为 1–28 的整数。')
  }
  if (form.value.quiet) {
    if (!integerInRange(form.value.quietStart, 0, 23) || !integerInRange(form.value.quietEnd, 0, 23)) {
      throw new Error('免打扰起止小时须为 0–23 的整数。')
    }
    if (form.value.quietStart.trim() === form.value.quietEnd.trim()) {
      throw new Error('免打扰起止小时不能相同。')
    }
    config.quiet_start = Number(form.value.quietStart.trim())
    config.quiet_end = Number(form.value.quietEnd.trim())
  }
  return config
}

async function savePlan(): Promise<void> {
  const target = current.value
  const key = pendingKey.value ?? newRequestId()
  pendingKey.value = key
  pendingAction.value = target === null ? 'create' : target.id
  await writeAction(async () => {
    const config = configPayload()
    const body: Record<string, unknown> = target === null
      ? { request_id: key, config, confirmed: true }
      : { version: target.version, action: 'edit', config, confirmed: true }
    const value = asObject<ScheduleOutput>(
      await apiPost(target === null ? shopPath('/schedules') : shopPath(`/schedules/${target.id}`), body),
    )
    if (value === null) throw new Error('保存响应无法读取，请到计划列表回读核对。')
    pendingKey.value = null
    pendingAction.value = null
    current.value = value
    applyConfig(value.config)
    await load()
  }, '计划与运行记录已更新。', '计划列表')
}

/** 核对同次操作：创建用同一次 request_id 幂等重放；修改则先回读当前版本。 */
async function reconcilePending(): Promise<void> {
  const action = pendingAction.value
  if (action === null) {
    pendingKey.value = null
    return
  }
  if (typeof action === 'number') {
    pendingKey.value = null
    pendingAction.value = null
    await reloadPlan(action)
    return
  }
  await savePlan()
}

async function control(plan: ScheduleOutput, action: 'pause' | 'resume' | 'revoke'): Promise<void> {
  const labels: Record<string, string> = { pause: '暂停', resume: '恢复', revoke: '撤销' }
  const modal = await Taro.showModal({
    title: `${labels[action]}计划`,
    content: `计划 #${plan.id} · ${plan.config.name}，操作后回读当前状态。`,
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<ScheduleOutput>(
      await apiPost(shopPath(`/schedules/${plan.id}`), { version: plan.version, action }),
    )
    if (value === null) throw new Error('操作响应无法读取，请回读计划核对。')
    await load()
  }, '计划与运行记录已更新。', '计划列表')
}

async function runCheck(plan: ScheduleOutput): Promise<void> {
  const modal = await Taro.showModal({
    title: '立即执行一次',
    content: '按此计划范围运行本地巡检或保存报表，结果进入运行历史。',
    confirmText: '运行',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    await apiPost(shopPath(`/schedules/${plan.id}/check`), {
      request_id: newRequestId(),
      version: plan.version,
    })
    await load()
  }, '已提交一次立即运行，请到运行历史核对结果。', '运行历史')
}

async function markRead(itemId: number): Promise<void> {
  await writeAction(async () => {
    await apiPost(shopPath(`/schedules/history/${itemId}/read`))
    await load()
  }, '通知已标记为已读。', '运行历史')
}
</script>
